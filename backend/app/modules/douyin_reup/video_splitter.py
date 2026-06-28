from __future__ import annotations

import logging
import re
from pathlib import Path
from app.adapters.ffmpeg_adapter import run_ffmpeg, probe_video
from app.utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


class SRTBlock:
    def __init__(self, index: int, start: float, end: float, text: str) -> None:
        self.index = index
        self.start = start
        self.end = end
        self.text = text


def parse_srt(srt_path: str) -> list[SRTBlock]:
    """Parse file SRT và trả về danh sách các block phụ đề với thời gian tính bằng giây."""
    path = Path(srt_path)
    if not path.exists() or path.stat().st_size == 0:
        return []

    content = path.read_text(encoding="utf-8", errors="replace")
    # Tách các block bằng dòng trống
    raw_blocks = re.split(r"\n\s*\n", content.strip())
    blocks = []

    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0])
            time_match = re.match(
                r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
                lines[1],
            )
            if not time_match:
                continue

            # Convert sang giây
            start = (
                int(time_match.group(1)) * 3600
                + int(time_match.group(2)) * 60
                + int(time_match.group(3))
                + int(time_match.group(4)) / 1000.0
            )
            end = (
                int(time_match.group(5)) * 3600
                + int(time_match.group(6)) * 60
                + int(time_match.group(7))
                + int(time_match.group(8)) / 1000.0
            )
            text = " ".join(lines[2:])
            blocks.append(SRTBlock(index, start, end, text))
        except Exception as exc:
            logger.warning(f"Lỗi phân tích block SRT: {exc}")
            continue

    return sorted(blocks, key=lambda b: b.start)


def plan_split_points(
    blocks: list[SRTBlock], video_duration: float, max_duration: float = 55.0
) -> list[tuple[float, float]]:
    """Lập kế hoạch chia nhỏ video dựa trên khoảng nghỉ giữa các câu thoại.
    Đảm bảo thời lượng mỗi phần <= max_duration và không cắt ngang câu nói.
    """
    if video_duration <= max_duration:
        return [(0.0, video_duration)]

    split_points = []
    current_start = 0.0

    while current_start < video_duration:
        # Thời gian nhắm tới cho điểm cắt tiếp theo
        target_end = current_start + max_duration

        if target_end >= video_duration:
            split_points.append((current_start, video_duration))
            break

        # Tìm block phụ đề tốt nhất kết thúc trước target_end
        best_cut_point = -1.0
        
        # Duyệt qua các block để tìm khoảng lặng (silence gap) tốt nhất
        for i in range(len(blocks) - 1):
            block = blocks[i]
            next_block = blocks[i + 1]

            # Đảm bảo block này nằm trong khoảng tìm kiếm của tập hiện tại
            if block.end > current_start and block.end <= target_end:
                # Ưu tiên các khoảng trống lớn giữa hai câu nói
                gap = next_block.start - block.end
                
                # Nếu có khoảng lặng trống, cắt ở giữa khoảng lặng
                if gap >= 0.3:
                    candidate = block.end + (gap / 2.0)
                    if candidate <= target_end:
                        best_cut_point = candidate
                else:
                    # Nếu khoảng lặng hẹp, cắt sát sau câu nói
                    if block.end <= target_end:
                        best_cut_point = block.end

        # Nếu không tìm thấy block nào phù hợp (không có sub hoặc sub quá dài), chia đều cơ học
        if best_cut_point <= current_start:
            best_cut_point = target_end

        # Đảm bảo điểm cắt thực sự di chuyển lên phía trước để tránh lặp vô hạn
        if best_cut_point <= current_start + 5.0:
            best_cut_point = min(video_duration, current_start + max_duration)

        split_points.append((current_start, best_cut_point))
        current_start = best_cut_point

    return split_points


def _normalize_color(hex_str: str) -> str:
    cleaned = hex_str.strip().lower()
    if cleaned.startswith("#"):
        cleaned = cleaned[1:]
    if len(cleaned) == 6:
        return f"0x{cleaned}"
    return "white"


def split_and_overlay_parts(
    video_path: str,
    srt_path: str | None,
    output_dir: str,
    *,
    max_duration: float = 55.0,
    part_prefix: str = "Phần",
    label_duration_mode: str = "always",
    position: str = "top_center",
    font_size: int = 48,
    font_color: str = "#ffffff",
    bg_color: str = "#000000",
    bg_opacity: float = 0.5,
) -> list[str]:
    """Cắt nhỏ video dài và vẽ nhãn Tập/Phần đè lên từng tập con bằng FFmpeg."""
    ensure_dir(output_dir)
    try:
        media = probe_video(video_path)
        video_duration = media.duration
    except Exception as exc:
        logger.error(f"Không thể probe thông tin video: {exc}")
        return []

    # 1. Lấy danh sách phụ đề và tính toán điểm cắt thông minh
    blocks = parse_srt(srt_path) if srt_path else []
    split_points = plan_split_points(blocks, video_duration, max_duration)

    logger.info(f"Kế hoạch chia tập video dài: {len(split_points)} phần từ {video_path}")

    # 2. Xử lý vẽ nhãn
    font_color_ff = _normalize_color(font_color)
    bg_color_ff = _normalize_color(bg_color)

    # Vị trí chữ đè
    x_expr = "(w-text_w)/2"
    y_expr = "60"
    if position == "bottom_center":
        y_expr = "h-text_h-120"
    elif position == "top_left":
        x_expr = "60"
        y_expr = "60"
    elif position == "top_right":
        x_expr = "w-text_w-60"
        y_expr = "60"

    # Điều kiện hiển thị 5s đầu hay toàn bộ
    enable_filter = ""
    if label_duration_mode == "intro_5s":
        enable_filter = ":enable='lt(t,5)'"

    output_files = []
    source_stem = Path(video_path).stem

    for idx, (start, end) in enumerate(split_points, 1):
        part_duration = end - start
        part_name = f"{part_prefix} {idx}"
        output_filename = f"{source_stem}_tap_{idx:02d}.mp4"
        output_path = Path(output_dir) / output_filename

        # Filter vẽ chữ đè
        drawtext_filter = (
            f"drawtext=text='{part_name}':fontcolor={font_color_ff}:fontsize={font_size}:"
            f"box=1:boxcolor={bg_color_ff}@{bg_opacity:.2f}:boxborderw=8:"
            f"x={x_expr}:y={y_expr}{enable_filter}"
        )

        args = [
            "-y",
            "-ss", f"{start:.3f}",
            "-t", f"{part_duration:.3f}",
            "-i", video_path,
            "-vf", drawtext_filter,
            "-c:v", "libx264",
            "-preset", "superfast",  # Sử dụng superfast preset để tối ưu tốc độ cho CPU
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path)
        ]

        logger.info(f"Cắt tập {idx}/{len(split_points)}: {start:.1f}s -> {end:.1f}s")
        try:
            run_ffmpeg(args)
            output_files.append(str(output_path.resolve()))
        except Exception as exc:
            logger.error(f"Lỗi khi cắt tập {idx}: {exc}")
            continue

    return output_files
