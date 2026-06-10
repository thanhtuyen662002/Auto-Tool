from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import run_ffmpeg


def make_video(
    path: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    duration: float = 3.0,
    fps: int = 24,
    with_audio: bool = True,
    audio_volume: float = 1.0,
    video_codec: str = "libx264",
) -> Path:
    args = [
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=blue:s={width}x{height}:d={duration}:r={fps}",
    ]
    if with_audio:
        args.extend(["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"])
        args.extend(["-filter:a", f"volume={audio_volume}", "-shortest"])
    args.extend(["-c:v", video_codec])
    if video_codec == "libx264":
        args.extend(["-preset", "ultrafast"])
    args.extend(["-pix_fmt", "yuv420p"])
    if with_audio:
        args.extend(["-c:a", "aac"])
    else:
        args.append("-an")
    args.append(str(path))
    run_ffmpeg(args)
    return path
