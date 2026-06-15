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
        max_frames: int = 240,
    ) -> list[tuple[int, str]]:
        media = probe_video(video_path)
        fps = max(0.1, float(sample_fps or 2.0))
        frame_limit = max(1, int(max_frames))
        target_dir = ensure_dir(output_dir)
        output_pattern = target_dir / "sample_%06d.jpg"
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(Path(video_path).expanduser().resolve()),
                "-vf",
                f"fps={fps:.6f},scale='min(720,iw)':-2",
                "-frames:v",
                str(frame_limit),
                "-q:v",
                "3",
                str(output_pattern),
            ]
        )

        duration_ms = max(1, int(round(media.duration * 1000)))
        interval_ms = max(1, int(round(1000 / fps)))
        sampled: list[tuple[int, str]] = []
        for index, frame_path in enumerate(sorted(target_dir.glob("sample_*.jpg"))):
            if frame_path.stat().st_size <= 0:
                continue
            timestamp_ms = min(duration_ms - 1, index * interval_ms)
            timestamp_path = target_dir / f"frame_{timestamp_ms:08d}ms.jpg"
            frame_path.replace(timestamp_path)
            sampled.append((timestamp_ms, str(timestamp_path)))
        return sampled
