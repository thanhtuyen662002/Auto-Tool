from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from app.modules.final_output_qa.final_output_qa_schema import VideoProbeInfo
from app.utils.dependency_manager import DependencyError, resolve_tool


class VideoProbeService:
    def probe_video(self, video_path: str) -> VideoProbeInfo:
        path = Path(video_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            return VideoProbeInfo(path=str(path), exists=False, readable=False, error="Video file does not exist.")
        try:
            ffprobe = resolve_tool("ffprobe")
            result = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries",
                    "format=duration,bit_rate,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration",
                    "-of", "json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "ffprobe failed.")
            data = json.loads(result.stdout)
            streams = data.get("streams") or []
            video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
            if not video_stream:
                raise RuntimeError("No readable video stream found.")
            audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), None)
            format_data = data.get("format") or {}
            duration = _float(video_stream.get("duration") or format_data.get("duration"))
            return VideoProbeInfo(
                path=str(path),
                exists=True,
                readable=True,
                duration=duration,
                width=_int(video_stream.get("width")),
                height=_int(video_stream.get("height")),
                fps=_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
                video_codec=str(video_stream.get("codec_name") or "") or None,
                audio_codec=str(audio_stream.get("codec_name") or "") or None if audio_stream else None,
                has_audio=audio_stream is not None,
                bitrate=_int(format_data.get("bit_rate")),
                file_size_mb=round(path.stat().st_size / (1024 * 1024), 3),
            )
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError, DependencyError) as exc:
            return VideoProbeInfo(
                path=str(path),
                exists=True,
                readable=False,
                file_size_mb=round(path.stat().st_size / (1024 * 1024), 3),
                error=str(exc),
            )


def _fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        result = float(Fraction(value))
        return round(result, 3) if result > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def _float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
