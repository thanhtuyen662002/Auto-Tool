from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_video, run_ffmpeg
from app.modules.douyin_reup.bgm_mixer import BGMMixer
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.subtitle_review import ApproveSubtitleDocumentRequest, SubtitleReviewService, SubtitleReviewStatus
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
        return self._render_video_with_subtitle(
            video=video,
            subtitle_srt_path=translation_result.translated_srt_path,
            subtitle_ass_path_override=None,
            warnings=list(translation_result.warnings),
            settings=settings,
            output_dir=output_dir,
            output_name=output_name,
            voiceover_path=None,
        )

    def render_video_with_srt(
        self,
        video: DouyinVideoItem,
        subtitle_srt_path: str,
        settings: DouyinReupSettings,
        output_dir: str,
        output_name: str,
        warnings: list[str] | None = None,
        voiceover_path: str | None = None,
    ) -> dict:
        return self._render_video_with_subtitle(
            video=video,
            subtitle_srt_path=subtitle_srt_path,
            subtitle_ass_path_override=None,
            warnings=list(warnings or []),
            settings=settings,
            output_dir=output_dir,
            output_name=output_name,
            voiceover_path=voiceover_path,
        )

    def render_from_review_document(
        self,
        document_id: str,
        settings: DouyinReupSettings,
        output_dir: str,
        voiceover_path: str | None = None,
    ) -> dict:
        service = SubtitleReviewService()
        document = service.get_document(document_id)
        if document.status != SubtitleReviewStatus.approved:
            raise ValueError("Subtitle review document must be approved before render.")
        if not document.corrected_srt_path:
            document = service.approve_document(
                document_id,
                ApproveSubtitleDocumentRequest(
                    generate_ass=not bool(document.corrected_ass_path),
                    visual_style_preset_id=settings.visual_style_preset_id,
                ),
            )
        media = probe_video(document.video_path)
        video = DouyinVideoItem(
            path=document.video_path,
            filename=Path(document.video_path).name,
            duration=media.duration,
            width=media.width,
            height=media.height,
            fps=media.fps,
            has_audio=media.has_audio,
        )
        result = self._render_video_with_subtitle(
            video=video,
            subtitle_srt_path=document.corrected_srt_path or document.translated_srt_path,
            subtitle_ass_path_override=document.corrected_ass_path,
            warnings=[],
            settings=settings,
            output_dir=output_dir,
            output_name=f"{Path(document.video_path).stem}_reviewed.mp4",
            voiceover_path=voiceover_path,
        )
        result.update(
            {
                "source_srt_file": document.source_srt_path,
                "translated_srt_file": document.translated_srt_path,
                "corrected_srt_file": document.corrected_srt_path,
                "corrected_ass_file": document.corrected_ass_path,
            }
        )
        return result

    def _render_video_with_subtitle(
        self,
        video: DouyinVideoItem,
        subtitle_srt_path: str,
        subtitle_ass_path_override: str | None,
        warnings: list[str],
        settings: DouyinReupSettings,
        output_dir: str,
        output_name: str,
        voiceover_path: str | None,
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
        errors: list[str] = []

        if settings.add_overlay:
            build_overlay_asset(preset, width, height, str(overlay_path))
        else:
            overlay_path = None  # type: ignore[assignment]

        subtitle_blocks = parse_srt_blocks(subtitle_srt_path)
        subtitle_lines = [
            {"start_hint": block.start, "end_hint": block.end, "text": block.text}
            for block in subtitle_blocks
        ]
        if settings.burn_subtitle and subtitle_ass_path_override and Path(subtitle_ass_path_override).exists():
            subtitle_ass_path = Path(subtitle_ass_path_override)
        elif settings.burn_subtitle and subtitle_lines:
            generate_ass_subtitle(subtitle_lines, preset, width, height, str(subtitle_ass_path))
        else:
            subtitle_ass_path = None  # type: ignore[assignment]
            if settings.burn_subtitle:
                warnings.append("Không có subtitle hợp lệ để burn vào video.")

        bgm_path = self.bgm_mixer.pick_bgm(settings.music_folder) if settings.add_bgm else None
        if settings.add_bgm and settings.music_folder and not bgm_path:
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
                voiceover_path=voiceover_path,
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
                        voiceover_path=voiceover_path,
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
                        voiceover_path=voiceover_path,
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
                    voiceover_path=voiceover_path,
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
            "voiceover_file": voiceover_path,
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
        voiceover_path: str | None = None,
    ) -> None:
        args = ["-y", "-i", video.path]
        next_input_index = 1
        overlay_input_index: int | None = None
        bgm_input_index: int | None = None
        voice_input_index: int | None = None

        if overlay_path:
            overlay_input_index = next_input_index
            next_input_index += 1
            args.extend(["-loop", "1", "-i", overlay_path])
        if bgm_path:
            bgm_input_index = next_input_index
            next_input_index += 1
            args.extend(["-stream_loop", "-1", "-i", bgm_path])
        if voiceover_path:
            voice_input_index = next_input_index
            args.extend(["-i", voiceover_path])

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

        audio_filter, audio_label = self._build_audio_filter(
            has_original_audio=video.has_audio and settings.keep_original_audio,
            has_bgm=bgm_input_index is not None,
            has_voiceover=voice_input_index is not None,
            original_audio_volume=settings.original_audio_volume,
            bgm_volume=settings.bgm_volume,
            duration=video.duration,
            bgm_input_index=bgm_input_index,
            voice_input_index=voice_input_index,
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

    @staticmethod
    def _build_audio_filter(
        *,
        has_original_audio: bool,
        has_bgm: bool,
        has_voiceover: bool,
        original_audio_volume: float,
        bgm_volume: float,
        duration: float,
        bgm_input_index: int | None,
        voice_input_index: int | None,
    ) -> tuple[str, str | None]:
        filters: list[str] = []
        labels: list[str] = []
        if has_original_audio:
            filters.append(f"[0:a]volume={_clamp_volume(original_audio_volume):.3f}[a0]")
            labels.append("[a0]")
        if has_bgm and bgm_input_index is not None:
            fade_out_start = max(0.0, float(duration) - 0.8)
            filters.append(
                f"[{bgm_input_index}:a]volume={_clamp_volume(bgm_volume):.3f},"
                f"afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.3f}:d=0.8[a1]"
            )
            labels.append("[a1]")
        if has_voiceover and voice_input_index is not None:
            filters.append(f"[{voice_input_index}:a]volume=1.000,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[av]")
            labels.append("[av]")
        if not labels:
            return "", None
        if len(labels) == 1:
            return ";".join(filters) + f";{labels[0]}anull[aout]", "[aout]"
        return ";".join(filters) + f";{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0[aout]", "[aout]"


def _escape_filter_path(path: str) -> str:
    cleaned = str(Path(path).expanduser().resolve()).replace("\\", "/")
    return (
        cleaned.replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )


def _clamp_volume(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
