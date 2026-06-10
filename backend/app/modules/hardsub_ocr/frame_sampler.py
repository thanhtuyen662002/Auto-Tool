from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video, run_ffmpeg
from app.utils.file_utils import ensure_dir


class FrameSampler:
    def sample_frames(
        self,
        video_path: str,
        output_dir: str,
        sample_fps: float = 2.0,
        max_frames: int = 600,
    ) -> list[tuple[int, str]]:
        media = probe_video(video_path)
        fps = max(0.1, float(sample_fps or 2.0))
        frame_limit = max(1, int(max_frames))
        interval_ms = max(1, int(round(1000 / fps)))
        duration_ms = max(1, int(round(media.duration * 1000)))
        timestamps = list(range(0, duration_ms, interval_ms))[:frame_limit]
        target_dir = ensure_dir(output_dir)

        sampled: list[tuple[int, str]] = []
        for timestamp_ms in timestamps:
            output_path = target_dir / f"frame_{timestamp_ms:08d}ms.jpg"
            seconds = timestamp_ms / 1000
            run_ffmpeg(
                [
                    "-y",
                    "-ss",
                    f"{seconds:.3f}",
                    "-i",
                    str(Path(video_path).expanduser().resolve()),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    "-vf",
                    "scale='min(720,iw)':-2",
                    str(output_path),
                ]
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                sampled.append((timestamp_ms, str(output_path)))
        return sampled
