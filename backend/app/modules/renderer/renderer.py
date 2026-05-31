from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.ffmpeg_adapter import run_ffmpeg
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir


class Renderer:
    def render_timeline(
        self,
        timeline: Timeline,
        config: ProjectConfig,
        output_dir: str,
        base_name: str | None = None,
    ) -> str:
        output_name = base_name or f"video_{timeline.output_index:03d}"
        output_path = Path(output_dir) / f"{output_name}_visual.mp4"
        temp_dir = Path(output_dir) / "_temp" / output_name

        ensure_dir(temp_dir)
        clip_paths: list[Path] = []

        try:
            for clip_index, clip in enumerate(timeline.clips, start=1):
                clip_path = temp_dir / f"clip_{clip_index:03d}.mp4"
                self._render_clip(clip, clip_path, config)
                clip_paths.append(clip_path)

            concat_file = temp_dir / "concat.txt"
            concat_file.write_text(
                "\n".join(f"file '{path.as_posix()}'" for path in clip_paths) + "\n",
                encoding="utf-8",
            )

            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(output_path),
                ]
            )
        except Exception:
            raise
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return str(output_path)

    def _render_clip(self, clip: TimelineClip, output_path: Path, config: ProjectConfig) -> None:
        width, height = self._parse_resolution(config.render.resolution)
        fps = config.render.fps
        raw_duration = max(0.05, clip.end - clip.start)

        filters = [
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
            "setsar=1",
            f"fps={fps}",
            f"setpts=PTS/{clip.speed:.6f}",
        ]
        if config.effects.grain > 0:
            grain_strength = max(1, min(100, config.effects.grain))
            filters.append(f"noise=alls={grain_strength}:allf=t+u")

        run_ffmpeg(
            [
                "-y",
                "-ss",
                f"{clip.start:.3f}",
                "-t",
                f"{raw_duration:.3f}",
                "-i",
                clip.source_path,
                "-vf",
                ",".join(filters),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                str(output_path),
            ]
        )

    @staticmethod
    def _parse_resolution(value: str) -> tuple[int, int]:
        width, height = value.lower().split("x")
        return int(width), int(height)
