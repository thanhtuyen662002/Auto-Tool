from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_video, run_ffmpeg
from app.modules.douyin_reup.bgm_mixer import BGMMixer
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.visual_style.overlay_asset_builder import build_overlay_asset
from app.modules.visual_style.style_schema import VisualStyleSettings
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService, parse_resolution
from app.utils.file_utils import ensure_dir


class DouyinRenderPipeline:
    def __init__(self, bgm_mixer: BGMMixer | None = None) -> None:
        self.bgm_mixer = bgm_mixer or BGMMixer()

    def render_video_with_translated_subtitle(
        self,
        video: DouyinVideoItem,
        translation_result: TranslationResult,
        settings: DouyinReupSettings,
        output_dir: str,
        output_name: str,
    ) -> dict:
        target_dir = ensure_dir(output_dir)
        width, height = parse_resolution(settings.resolution)
        preset = VisualStyleService().resolve_preset(
            VisualStyleSettings(
                preset_id=settings.visual_style_preset_id,
                custom_overrides={"overlay": {"enabled": settings.add_overlay}},
            )
        )

        source_copy = target_dir / "source.mp4"
        if not source_copy.exists():
            try:
                shutil.copy2(video.path, source_copy)
            except OSError:
                source_copy = Path(video.path)

        overlay_path = target_dir / f"{Path(output_name).stem}_overlay.png"
        subtitle_ass_path = target_dir / f"{Path(output_name).stem}_vi.ass"
        output_path = target_dir / output_name
        warnings = list(translation_result.warnings)
        errors: list[str] = []

        if settings.add_overlay:
            build_overlay_asset(preset, width, height, str(overlay_path))
        else:
            overlay_path = None  # type: ignore[assignment]

        subtitle_blocks = parse_srt_blocks(translation_result.translated_srt_path)
        subtitle_lines = [
            {"start_hint": block.start, "end_hint": block.end, "text": block.text}
            for block in subtitle_blocks
        ]
        if settings.burn_subtitle and subtitle_lines:
            generate_ass_subtitle(subtitle_lines, preset, width, height, str(subtitle_ass_path))
        else:
            subtitle_ass_path = None  # type: ignore[assignment]
            if settings.burn_subtitle:
                warnings.append("Không có subtitle hợp lệ để burn vào video.")

        bgm_path = self.bgm_mixer.pick_bgm(settings.music_folder)
        if settings.music_folder and not bgm_path:
            warnings.append(f"Không tìm thấy file nhạc nền hợp lệ trong thư mục: {settings.music_folder}")

        try:
            self._run_render(
                video=video,
                settings=settings,
                output_path=str(output_path),
                width=width,
                height=height,
                overlay_path=str(overlay_path) if overlay_path else None,
                subtitle_ass_path=str(subtitle_ass_path) if subtitle_ass_path else None,
                bgm_path=bgm_path,
            )
        except FFmpegError as exc:
            if subtitle_ass_path:
                warnings.append(f"Burn subtitle thất bại, thử render lại không subtitle: {exc}")
                try:
                    self._run_render(
                        video=video,
                        settings=settings,
                        output_path=str(output_path),
                        width=width,
                        height=height,
                        overlay_path=str(overlay_path) if overlay_path else None,
                        subtitle_ass_path=None,
                        bgm_path=bgm_path,
                    )
                except FFmpegError as retry_exc:
                    if not bgm_path:
                        raise
                    warnings.append(f"Render với nhạc nền thất bại, thử render lại chỉ giữ audio gốc: {retry_exc}")
                    bgm_path = None
                    self._run_render(
                        video=video,
                        settings=settings,
                        output_path=str(output_path),
                        width=width,
                        height=height,
                        overlay_path=str(overlay_path) if overlay_path else None,
                        subtitle_ass_path=None,
                        bgm_path=None,
                    )
                subtitle_ass_path = None  # type: ignore[assignment]
            elif bgm_path:
                warnings.append(f"Render với nhạc nền thất bại, thử render lại chỉ giữ audio gốc: {exc}")
                bgm_path = None
                self._run_render(
                    video=video,
                    settings=settings,
                    output_path=str(output_path),
                    width=width,
                    height=height,
                    overlay_path=str(overlay_path) if overlay_path else None,
                    subtitle_ass_path=None,
                    bgm_path=None,
                )
            else:
                raise

        if not output_path.exists() or output_path.stat().st_size <= 0:
            errors.append("FFmpeg không tạo được video final hoặc file output bị rỗng.")
            raise RuntimeError(errors[-1])

        media = probe_video(str(output_path))
        return {
            "path": str(output_path),
            "duration": media.duration,
            "source_video": str(source_copy),
            "subtitle_ass_file": str(subtitle_ass_path) if subtitle_ass_path else None,
            "overlay_file": str(overlay_path) if overlay_path else None,
            "bgm_file": bgm_path,
            "warnings": warnings,
            "errors": errors,
        }

    def _run_render(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        output_path: str,
        width: int,
        height: int,
        overlay_path: str | None,
        subtitle_ass_path: str | None,
        bgm_path: str | None,
    ) -> None:
        args = ["-y", "-i", video.path]
        overlay_input_index: int | None = None
        bgm_input_index: int | None = None

        if overlay_path:
            overlay_input_index = 1
            args.extend(["-loop", "1", "-i", overlay_path])
        if bgm_path:
            bgm_input_index = 2 if overlay_input_index is not None else 1
            args.extend(["-stream_loop", "-1", "-i", bgm_path])

        video_filters = [
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={settings.fps},setsar=1[v0]"
        ]
        current_label = "[v0]"
        if overlay_input_index is not None:
            video_filters.append(
                f"[{overlay_input_index}:v]format=rgba,scale={width}:{height}[ov];"
                f"{current_label}[ov]overlay=0:0:eof_action=repeat:shortest=0:repeatlast=1[v1]"
            )
            current_label = "[v1]"
        if subtitle_ass_path:
            video_filters.append(f"{current_label}ass=filename='{_escape_filter_path(subtitle_ass_path)}'[vout]")
        else:
            video_filters.append(f"{current_label}null[vout]")

        audio_filter = ""
        audio_label: str | None = None
        if video.has_audio or bgm_input_index is not None:
            audio_filter, audio_label = self.bgm_mixer.build_audio_filter(
                has_original_audio=video.has_audio,
                has_bgm=bgm_input_index is not None,
                original_audio_volume=settings.original_audio_volume,
                bgm_volume=settings.bgm_volume,
                duration=video.duration,
                bgm_input_index=bgm_input_index or 1,
            )

        filter_complex = ";".join(part for part in [*video_filters, audio_filter] if part)
        args.extend(["-filter_complex", filter_complex, "-map", "[vout]"])
        if audio_label:
            args.extend(["-map", audio_label, "-c:a", "aac", "-b:a", "160k"])
        else:
            args.append("-an")
        args.extend(
            [
                "-t",
                f"{video.duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                output_path,
            ]
        )
        run_ffmpeg(args)


def _escape_filter_path(path: str) -> str:
    cleaned = str(Path(path).expanduser().resolve()).replace("\\", "/")
    return (
        cleaned.replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )
