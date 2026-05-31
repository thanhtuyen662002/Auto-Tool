from __future__ import annotations

import json
import subprocess
from fractions import Fraction
from pathlib import Path

from app.schemas.media_schema import MediaFile
from app.utils.dependency_manager import DependencyError, resolve_tool


class FFmpegError(RuntimeError):
    """Raised when ffmpeg or ffprobe fails."""


class MissingFFmpegError(FFmpegError):
    """Raised when ffmpeg or ffprobe is not available."""


def _run_process(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        command = [resolve_tool(command[0]), *command[1:]]
    except DependencyError as exc:
        raise MissingFFmpegError(str(exc)) from exc

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise MissingFFmpegError(f"Command not found: {command[0]}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or "No process output was captured."
        raise FFmpegError(f"Command failed ({' '.join(command)}):\n{details}")
    return result


def _parse_fps(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe_video(path: str) -> MediaFile:
    video_path = Path(path).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=index,codec_type,width,height,avg_frame_rate,r_frame_rate,duration",
        "-of",
        "json",
        str(video_path),
    ]
    result = _run_process(command)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise FFmpegError(f"ffprobe returned invalid JSON for {video_path}") from exc

    streams = data.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise FFmpegError(f"No video stream found in file: {video_path}")

    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    format_data = data.get("format", {})

    duration_value = video_stream.get("duration") or format_data.get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as exc:
        raise FFmpegError(f"Could not read duration for video: {video_path}") from exc

    fps = _parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(video_stream.get("r_frame_rate"))
    if fps <= 0:
        raise FFmpegError(f"Could not read FPS for video: {video_path}")

    return MediaFile(
        path=str(video_path),
        duration=duration,
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        fps=fps,
        has_audio=audio_stream is not None,
        format_name=str(format_data.get("format_name") or ""),
    )


def probe_media_duration(path: str) -> float:
    media_path = Path(path).expanduser().resolve()
    if not media_path.exists():
        raise FileNotFoundError(f"Media file does not exist: {media_path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    result = _run_process(command)

    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise FFmpegError(f"Could not read media duration for: {media_path}") from exc

    if duration <= 0:
        raise FFmpegError(f"Media duration must be greater than 0: {media_path}")
    return duration


def run_ffmpeg(args: list[str]) -> None:
    if not args:
        raise ValueError("run_ffmpeg requires at least one ffmpeg argument")

    command = args if Path(args[0]).stem.lower() == "ffmpeg" else ["ffmpeg", *args]
    _run_process(command)
