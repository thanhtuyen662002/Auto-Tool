from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.crop_safety.crop_strategy import build_crop_video_filter
from app.modules.timeline_builder.timeline_builder import ClipType, Timeline, TimelineClip
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
                "\n".join(f"file '{path.name}'" for path in clip_paths) + "\n",
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
        from app.modules.renderer.special_clip_renderer import SpecialClipRenderer

        width, height = self._parse_resolution(config.render.resolution)
        fps = config.render.fps

        # Route SESE special clips (FREEZE / FREEZE_ZOOM) to SpecialClipRenderer
        if clip.clip_type in (ClipType.FREEZE, ClipType.FREEZE_ZOOM):
            SpecialClipRenderer.render(
                clip=clip,
                output_path=output_path,
                width=width,
                height=height,
                fps=fps,
                grain=config.effects.grain,
            )
            return

        # Normal clip rendering
        raw_duration = max(0.05, clip.end - clip.start)

        filtergraph = build_crop_video_filter(
            crop_mode=clip.crop_mode,
            crop_box=clip.crop_box,
            target_width=width,
            target_height=height,
            fps=fps,
            speed=clip.speed,
            grain=config.effects.grain,
        )
        try:
            self._run_render_clip_ffmpeg(clip, output_path, raw_duration, fps, filtergraph)
        except FFmpegError:
            fallback_filter = build_crop_video_filter(
                crop_mode="center_crop",
                crop_box=None,
                target_width=width,
                target_height=height,
                fps=fps,
                speed=clip.speed,
                grain=config.effects.grain,
            )
            self._run_render_clip_ffmpeg(clip, output_path, raw_duration, fps, fallback_filter)

    @staticmethod
    def _run_render_clip_ffmpeg(
        clip: TimelineClip,
        output_path: Path,
        raw_duration: float,
        fps: int,
        filtergraph: str,
    ) -> None:
        run_ffmpeg(
            [
                "-y",
                "-ss",
                f"{clip.start:.3f}",
                "-t",
                f"{raw_duration:.3f}",
                "-i",
                clip.source_path,
                "-filter_complex",
                filtergraph,
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
