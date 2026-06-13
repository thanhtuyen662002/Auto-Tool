from __future__ import annotations

import json
import subprocess
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from app.utils.dependency_manager import DependencyError, resolve_tool

from .source_media_schema import (
    SourceMediaItem,
    SourceMediaOrientation,
    SourceMediaQualityFlag,
    SourceMediaStatus,
    SourceMediaType,
)


class SourceMediaMetadataService:
    def probe_video(self, path: str) -> SourceMediaItem:
        video_path = Path(path).expanduser().resolve()
        base = self._base_item(video_path)
        if not video_path.exists():
            return base.model_copy(
                update={
                    "status": SourceMediaStatus.missing,
                    "selected": False,
                    "error_message": "Không tìm thấy file.",
                    "quality_flags": [SourceMediaQualityFlag.unreadable],
                    "quality_score": 0,
                }
            )

        try:
            ffprobe = resolve_tool("ffprobe")
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate",
                    "-of",
                    "json",
                    str(video_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except (DependencyError, FileNotFoundError) as exc:
            return self._unreadable(base, f"Không thể đọc metadata vì thiếu ffprobe: {exc}")

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "ffprobe không trả về chi tiết lỗi.").strip()
            return self._unreadable(base, detail)

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return self._unreadable(base, "ffprobe trả về JSON không hợp lệ.")

        streams = payload.get("streams") or []
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if not video_stream:
            return self._unreadable(base, "Không tìm thấy video stream.")

        format_data = payload.get("format") or {}
        duration = _float_or_none(format_data.get("duration"))
        width = _int_or_none(video_stream.get("width"))
        height = _int_or_none(video_stream.get("height"))
        fps = _parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(video_stream.get("r_frame_rate"))
        bitrate = _int_or_none(format_data.get("bit_rate"))
        orientation = self.classify_orientation(width, height)
        aspect_ratio = round(width / height, 4) if width and height else None

        item = base.model_copy(
            update={
                "duration_seconds": duration,
                "width": width,
                "height": height,
                "fps": fps,
                "bitrate": bitrate,
                "codec": video_stream.get("codec_name"),
                "has_audio": audio_stream is not None,
                "orientation": orientation,
                "aspect_ratio": aspect_ratio,
            }
        )
        flags = self.detect_quality_flags(item)
        score = self.compute_quality_score(item)
        status = SourceMediaStatus.warning if flags else SourceMediaStatus.valid
        selected = SourceMediaQualityFlag.unreadable not in flags and SourceMediaQualityFlag.too_short not in flags
        warnings = [_flag_message(flag) for flag in flags if flag != SourceMediaQualityFlag.unreadable]
        return item.model_copy(
            update={
                "status": status,
                "quality_flags": flags,
                "quality_score": score,
                "selected": selected,
                "warnings": warnings,
                "excluded_reason": None if selected else "Video quá ngắn hoặc không đọc được.",
            }
        )

    def classify_orientation(self, width: int | None, height: int | None) -> SourceMediaOrientation:
        if not width or not height:
            return SourceMediaOrientation.unknown
        if abs(width - height) <= max(width, height) * 0.05:
            return SourceMediaOrientation.square
        if height > width:
            return SourceMediaOrientation.vertical
        return SourceMediaOrientation.horizontal

    def detect_quality_flags(self, item: SourceMediaItem) -> list[SourceMediaQualityFlag]:
        flags: list[SourceMediaQualityFlag] = []
        if item.status in {SourceMediaStatus.unreadable, SourceMediaStatus.missing}:
            flags.append(SourceMediaQualityFlag.unreadable)
        if item.duration_seconds is not None and item.duration_seconds < 3:
            flags.append(SourceMediaQualityFlag.too_short)
        if item.duration_seconds is not None and item.duration_seconds > 180:
            flags.append(SourceMediaQualityFlag.too_long)
        if (item.width and item.width < 720) or (item.height and item.height < 720):
            flags.append(SourceMediaQualityFlag.low_resolution)
        if item.orientation == SourceMediaOrientation.horizontal:
            flags.append(SourceMediaQualityFlag.horizontal_video)
        if item.orientation == SourceMediaOrientation.square:
            flags.append(SourceMediaQualityFlag.square_video)
        if item.has_audio is False:
            flags.append(SourceMediaQualityFlag.no_audio)
        if item.file_size_bytes > 2 * 1024 * 1024 * 1024:
            flags.append(SourceMediaQualityFlag.very_large_file)
        return flags

    def compute_quality_score(self, item: SourceMediaItem) -> float:
        score = 100.0
        flags = item.quality_flags or self.detect_quality_flags(item)
        if SourceMediaQualityFlag.unreadable in flags:
            score -= 30
        if SourceMediaQualityFlag.low_resolution in flags:
            score -= 20
        if SourceMediaQualityFlag.too_short in flags:
            score -= 15
        if SourceMediaQualityFlag.too_long in flags:
            score -= 10
        if SourceMediaQualityFlag.horizontal_video in flags:
            score -= 10
        if SourceMediaQualityFlag.no_audio in flags:
            score -= 5
        if SourceMediaQualityFlag.very_large_file in flags:
            score -= 5
        return max(0.0, min(100.0, round(score, 2)))

    def _base_item(self, path: Path) -> SourceMediaItem:
        stat = path.stat() if path.exists() else None
        return SourceMediaItem(
            id=source_media_id(str(path)),
            path=str(path),
            filename=path.name,
            extension=path.suffix.lower(),
            media_type=SourceMediaType.video,
            file_size_bytes=stat.st_size if stat else 0,
            created_at=_timestamp(stat.st_ctime) if stat else None,
            modified_at=_timestamp(stat.st_mtime) if stat else None,
        )

    def _unreadable(self, item: SourceMediaItem, message: str) -> SourceMediaItem:
        flags = [SourceMediaQualityFlag.unreadable]
        return item.model_copy(
            update={
                "status": SourceMediaStatus.unreadable,
                "selected": False,
                "quality_flags": flags,
                "quality_score": 0,
                "warnings": ["Không đọc được metadata video."],
                "error_message": message,
                "excluded_reason": "Không đọc được file.",
            }
        )


def source_media_id(path: str) -> str:
    import hashlib

    return "vid_" + hashlib.sha1(str(Path(path).expanduser().resolve()).encode("utf-8")).hexdigest()[:16]


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).replace(microsecond=0).isoformat()


def _parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        fps = float(Fraction(value))
        return round(fps, 3) if fps > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def _float_or_none(value) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _flag_message(flag: SourceMediaQualityFlag) -> str:
    messages = {
        SourceMediaQualityFlag.too_short: "Video ngắn dưới 3 giây.",
        SourceMediaQualityFlag.too_long: "Video dài hơn 180 giây.",
        SourceMediaQualityFlag.low_resolution: "Độ phân giải thấp.",
        SourceMediaQualityFlag.horizontal_video: "Video ngang, có thể cần crop/padding.",
        SourceMediaQualityFlag.square_video: "Video vuông, có thể cần crop/padding.",
        SourceMediaQualityFlag.no_audio: "Video không có audio.",
        SourceMediaQualityFlag.very_large_file: "File rất lớn, xử lý có thể chậm.",
    }
    return messages.get(flag, flag.value)
