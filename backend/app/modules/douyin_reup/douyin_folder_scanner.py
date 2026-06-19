from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_video
from app.modules.douyin_reup.douyin_schema import DouyinVideoItem
from app.utils.dependency_manager import DependencyError, resolve_tool
from app.utils.subprocess_utils import run_hidden

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
SIDECAR_SRT_SUFFIXES = (".srt", ".zh.srt", ".zh-cn.srt", ".cn.srt", ".zho.srt")


class DouyinFolderScanner:
    def __init__(self) -> None:
        self.total_files = 0
        self.invalid_files = 0
        self.errors: list[str] = []

    def scan_folder(self, folder_path: str) -> list[DouyinVideoItem]:
        folder = Path(folder_path).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục video Douyin: {folder}")

        files = [path for path in folder.iterdir() if path.is_file() and not path.name.startswith(".")]
        candidates = sorted(path for path in files if path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS)
        self.total_files = len(files)
        self.invalid_files = 0
        self.errors = []

        videos: list[DouyinVideoItem] = []
        for path in candidates:
            try:
                media = probe_video(str(path))
                warnings: list[str] = []
                if media.duration < 3:
                    warnings.append("Video ngắn hơn 3 giây, vẫn được giữ nhưng có thể không phù hợp để reup.")
                sidecar = find_sidecar_srt(path)
                videos.append(
                    DouyinVideoItem(
                        path=media.path,
                        filename=path.name,
                        duration=media.duration,
                        width=media.width,
                        height=media.height,
                        fps=media.fps,
                        has_audio=media.has_audio,
                        sidecar_srt_path=str(sidecar) if sidecar else None,
                        embedded_subtitle_found=has_embedded_text_subtitle(str(path)),
                        warnings=warnings,
                    )
                )
            except (OSError, FFmpegError, ValueError) as exc:
                self.invalid_files += 1
                message = f"Bỏ qua video không hợp lệ {path.name}: {exc}"
                self.errors.append(message)
                logger.warning(message)

        self.invalid_files += max(0, self.total_files - len(candidates))
        return videos


def find_sidecar_srt(video_path: str | Path) -> Path | None:
    path = Path(video_path)
    for suffix in SIDECAR_SRT_SUFFIXES:
        candidate = path.with_suffix(suffix)
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            return candidate.resolve()
    return None


def has_embedded_text_subtitle(video_path: str) -> bool:
    try:
        ffprobe = resolve_tool("ffprobe")
    except DependencyError:
        return False

    result = run_hidden(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index,codec_type,codec_name",
            "-of",
            "json",
            str(Path(video_path).expanduser().resolve()),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return False
    text_codecs = {"subrip", "ass", "ssa", "mov_text", "webvtt", "text"}
    return any(str(stream.get("codec_name") or "").lower() in text_codecs for stream in data.get("streams", []))
