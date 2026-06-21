from __future__ import annotations

import os
import re
import shutil
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_video, run_ffmpeg
from app.modules.douyin_reup.bgm_mixer import BGMMixer
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, TranslationResult
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks, write_srt_blocks
from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine, VoiceoverLine
from app.modules.subtitle_review import ApproveSubtitleDocumentRequest, SubtitleReviewService, SubtitleReviewStatus
from app.modules.tts.settings_builder import voiceover_tts_settings
from app.modules.tts.text_cleanup import estimate_voice_duration
from app.modules.tts.tts_schema import TTSSettings
from app.modules.visual_style.custom_overlay_asset import build_custom_overlay_asset, select_custom_overlay_asset
from app.modules.visual_style.overlay_asset_builder import build_overlay_asset
from app.modules.visual_style.style_schema import VisualStyleSettings
from app.modules.visual_style.subtitle_cover_detector import detect_subtitle_cover_from_ocr_debug
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService, parse_resolution
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.utils.file_utils import ensure_dir


VOICEOVER_AUDIO_GAIN = 1.8
MASTER_AUDIO_GAIN = 1.6
AUDIO_LIMITER_FILTER = "alimiter=limit=0.95"
MASTER_LOUDNESS_FILTER = f"volume={MASTER_AUDIO_GAIN:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,{AUDIO_LIMITER_FILTER}"
MIN_VIDEO_SLOWDOWN_DELTA = 0.015


def _visual_style_overrides(settings: DouyinReupSettings) -> dict:
    overrides: dict = {"overlay": {"enabled": settings.add_overlay}}
    if settings.subtitle_style_custom_enabled:
        overrides["subtitle"] = {
            "font_family": settings.subtitle_font_family,
            "font_size": settings.subtitle_font_size,
            "font_color": settings.subtitle_font_color,
            "stroke_color": settings.subtitle_stroke_color,
            "stroke_width": settings.subtitle_stroke_width,
            "shadow_enabled": settings.subtitle_shadow_enabled,
            "shadow_color": settings.subtitle_shadow_color,
            "shadow_opacity": settings.subtitle_shadow_opacity,
            "shadow_size": settings.subtitle_shadow_size,
            "max_chars_per_line": settings.subtitle_max_chars_per_line,
            "max_lines": settings.subtitle_max_lines,
            "position": settings.subtitle_position,
        }
    return overrides


class DouyinRenderPipeline:
    def __init__(self, bgm_mixer: BGMMixer | None = None, voice_generator: VoiceGenerator | None = None) -> None:
        self.bgm_mixer = bgm_mixer or BGMMixer()
        self.voice_generator = voice_generator or VoiceGenerator()

    def render_video_with_translated_subtitle(
        self,
        video: DouyinVideoItem,
        translation_result: TranslationResult,
        settings: DouyinReupSettings,
        output_dir: str,
        output_name: str,
        tts_settings: TTSSettings | None = None,
        source_ocr_debug_path: str | None = None,
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
            tts_settings=tts_settings,
            source_ocr_debug_path=source_ocr_debug_path,
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
        tts_settings: TTSSettings | None = None,
        source_ocr_debug_path: str | None = None,
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
            tts_settings=tts_settings,
            source_ocr_debug_path=source_ocr_debug_path,
        )

    def render_from_review_document(
        self,
        document_id: str,
        settings: DouyinReupSettings,
        output_dir: str,
        voiceover_path: str | None = None,
        tts_settings: TTSSettings | None = None,
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
            tts_settings=tts_settings,
            source_ocr_debug_path=None,
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
        tts_settings: TTSSettings | None,
        source_ocr_debug_path: str | None,
    ) -> dict:
        target_dir = ensure_dir(output_dir)
        width, height = parse_resolution(settings.resolution)
        preset = VisualStyleService().resolve_preset(
            VisualStyleSettings(
                preset_id=settings.visual_style_preset_id,
                custom_overrides=_visual_style_overrides(settings),
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

        overlay_mode = "none" if not settings.add_overlay else settings.overlay_mode
        if overlay_mode == "preset":
            build_overlay_asset(preset, width, height, str(overlay_path))
        elif overlay_mode == "custom":
            custom_overlay_source = select_custom_overlay_asset(settings.custom_overlay_path)
            build_custom_overlay_asset(
                source_path=custom_overlay_source,
                output_path=str(overlay_path),
                width=width,
                height=height,
                height_percent=settings.custom_overlay_height_percent,
                fit_mode=settings.custom_overlay_fit_mode,
            )
        else:
            overlay_path = None  # type: ignore[assignment]

        subtitle_blocks = parse_srt_blocks(subtitle_srt_path)
        render_duration = float(video.duration)
        video_slowdown_factor = 1.0
        render_subtitle_srt_path: str | None = None
        voiceover_timing: dict | None = None
        voiceover_subtitle_srt_path = subtitle_srt_path
        if settings.generate_voiceover_for_silent_video:
            voiceover_timing = _plan_voiceover_video_slowdown(
                subtitle_blocks,
                settings=settings,
                target_duration=render_duration,
            )
            video_slowdown_factor = float(voiceover_timing.get("slowdown_factor") or 1.0)
            if video_slowdown_factor > 1.0 + MIN_VIDEO_SLOWDOWN_DELTA:
                render_duration = round(render_duration * video_slowdown_factor, 3)
                subtitle_blocks = _scale_subtitle_blocks(
                    subtitle_blocks,
                    scale=video_slowdown_factor,
                    target_duration=render_duration,
                )
                render_subtitle_srt_path = str(target_dir / f"{Path(output_name).stem}_vi_voice_timing.srt")
                write_srt_blocks(subtitle_blocks, render_subtitle_srt_path)
                voiceover_subtitle_srt_path = render_subtitle_srt_path
                voiceover_timing["scaled_duration"] = render_duration
                warnings.append(
                    "voiceover_video_slowdown: Tiếng Việt cần nhiều thời gian đọc hơn subtitle gốc, "
                    f"đã tua chậm video/timeline {video_slowdown_factor:.2f}x để giảm ép tốc độ voice."
                )
        cover_reference_blocks = list(subtitle_blocks)
        if voiceover_path is None and settings.generate_voiceover_for_silent_video:
            voiceover_path = self._generate_voiceover_from_srt(
                subtitle_srt_path=voiceover_subtitle_srt_path,
                output_dir=str(target_dir),
                output_name=output_name,
                settings=settings,
                target_duration=render_duration,
                tts_settings=tts_settings,
            )
            warnings.extend(self.voice_generator.warnings)
            if self.voice_generator.last_subtitle_timeline:
                voice_synced_blocks = [
                    SubtitleBlock(
                        index=index,
                        start=float(line.start_hint or 0.0),
                        end=float(line.end_hint or 0.0),
                        text=line.text,
                    )
                    for index, line in enumerate(self.voice_generator.last_subtitle_timeline, start=1)
                    if (line.end_hint or 0) > (line.start_hint or 0) and line.text.strip()
                ]
                if voice_synced_blocks:
                    subtitle_blocks = voice_synced_blocks
                    render_subtitle_srt_path = str(target_dir / f"{Path(output_name).stem}_vi_voice_synced.srt")
                    write_srt_blocks(subtitle_blocks, render_subtitle_srt_path)
                    warnings.append(
                        "voiceover_subtitle_sync: Phụ đề Việt đã được canh theo timeline giọng đọc để tránh tiếng và chữ lệch nhau."
                    )
        subtitle_lines = [
            {"start_hint": block.start, "end_hint": block.end, "text": block.text}
            for block in subtitle_blocks
        ]
        subtitle_cover_options = (
            self._subtitle_cover_options(
                settings=settings,
                video=video,
                source_ocr_debug_path=source_ocr_debug_path,
                warnings=warnings,
            )
            if settings.burn_subtitle and settings.subtitle_cover_enabled
            else None
        )
        if settings.burn_subtitle and subtitle_ass_path_override and Path(subtitle_ass_path_override).exists():
            subtitle_ass_path = Path(subtitle_ass_path_override)
        elif settings.burn_subtitle and subtitle_lines:
            cover_options = dict(subtitle_cover_options or {})
            cover_options["cover_background_reference_lines"] = [
                {"start_hint": block.start, "end_hint": block.end, "text": block.text}
                for block in cover_reference_blocks
            ]
            if settings.subtitle_cover_mode == "blur":
                cover_options["cover_background_draw"] = False
            generate_ass_subtitle(
                subtitle_lines,
                preset,
                width,
                height,
                str(subtitle_ass_path),
                **cover_options,
            )
        else:
            subtitle_ass_path = None  # type: ignore[assignment]
            if settings.burn_subtitle:
                raise RuntimeError("Đã bật burn subtitle nhưng không có subtitle hợp lệ để đưa vào video.")

        bgm_path = None
        if settings.add_bgm:
            if not settings.music_folder:
                if not _allow_render_without_bgm():
                    raise RuntimeError("Đã bật nhạc nền nhưng chưa chọn thư mục nhạc.")
                warnings.append("Đã bật nhạc nền nhưng chưa chọn thư mục nhạc nên video không có BGM.")
            else:
                bgm_path = self.bgm_mixer.pick_bgm(settings.music_folder, settings.favorite_music_paths)
                if not bgm_path:
                    if not _allow_render_without_bgm():
                        raise RuntimeError(f"Không tìm thấy file nhạc nền hợp lệ trong thư mục: {settings.music_folder}")
                    warnings.append(f"Không tìm thấy file nhạc nền hợp lệ trong thư mục: {settings.music_folder}")

        try:
            self._run_render_with_audio_fallback(
                video=video,
                settings=settings,
                output_path=str(output_path),
                width=width,
                height=height,
                overlay_path=str(overlay_path) if overlay_path else None,
                subtitle_ass_path=str(subtitle_ass_path) if subtitle_ass_path else None,
                bgm_path=bgm_path,
                voiceover_path=voiceover_path,
                render_duration=render_duration,
                video_slowdown_factor=video_slowdown_factor,
                subtitle_cover_options=subtitle_cover_options if settings.subtitle_cover_mode == "blur" else None,
                warnings=warnings,
            )
        except FFmpegError as exc:
            if subtitle_ass_path:
                if not _allow_render_without_subtitle():
                    raise FFmpegError(
                        "Burn subtitle thất bại nên dừng render để tránh xuất video không có phụ đề. "
                        f"Chi tiết: {exc}"
                    ) from exc
                warnings.append(f"Burn subtitle thất bại, thử render lại không subtitle: {exc}")
                try:
                    self._run_render_with_audio_fallback(
                        video=video,
                        settings=settings,
                        output_path=str(output_path),
                        width=width,
                        height=height,
                        overlay_path=str(overlay_path) if overlay_path else None,
                        subtitle_ass_path=None,
                        bgm_path=bgm_path,
                        voiceover_path=voiceover_path,
                        render_duration=render_duration,
                        video_slowdown_factor=video_slowdown_factor,
                        subtitle_cover_options=None,
                        warnings=warnings,
                    )
                except FFmpegError as retry_exc:
                    if not bgm_path:
                        raise
                    if not _allow_render_without_bgm():
                        raise FFmpegError(
                            "Render với nhạc nền thất bại nên dừng render để tránh xuất video thiếu nhạc. "
                            f"Chi tiết: {retry_exc}"
                        ) from retry_exc
                    warnings.append(f"Render với nhạc nền thất bại, thử render lại chỉ giữ audio gốc: {retry_exc}")
                    bgm_path = None
                    self._run_render_with_audio_fallback(
                        video=video,
                        settings=settings,
                        output_path=str(output_path),
                        width=width,
                        height=height,
                        overlay_path=str(overlay_path) if overlay_path else None,
                        subtitle_ass_path=None,
                        bgm_path=None,
                        voiceover_path=voiceover_path,
                        render_duration=render_duration,
                        video_slowdown_factor=video_slowdown_factor,
                        subtitle_cover_options=None,
                        warnings=warnings,
                    )
                subtitle_ass_path = None  # type: ignore[assignment]
            elif bgm_path:
                if not _allow_render_without_bgm():
                    raise FFmpegError(
                        "Render với nhạc nền thất bại nên dừng render để tránh xuất video thiếu nhạc. "
                        f"Chi tiết: {exc}"
                    ) from exc
                warnings.append(f"Render với nhạc nền thất bại, thử render lại chỉ giữ audio gốc: {exc}")
                bgm_path = None
                self._run_render_with_audio_fallback(
                    video=video,
                    settings=settings,
                    output_path=str(output_path),
                    width=width,
                    height=height,
                    overlay_path=str(overlay_path) if overlay_path else None,
                    subtitle_ass_path=None,
                    bgm_path=None,
                    voiceover_path=voiceover_path,
                    render_duration=render_duration,
                    video_slowdown_factor=video_slowdown_factor,
                    subtitle_cover_options=None,
                    warnings=warnings,
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
            "render_subtitle_srt_file": render_subtitle_srt_path,
            "video_slowdown_factor": video_slowdown_factor,
            "voiceover_timing": voiceover_timing,
            "warnings": warnings,
            "errors": errors,
        }

    def _generate_voiceover_from_srt(
        self,
        *,
        subtitle_srt_path: str,
        output_dir: str,
        output_name: str,
        settings: DouyinReupSettings,
        target_duration: float,
        tts_settings: TTSSettings | None = None,
    ) -> str:
        blocks = [block for block in parse_srt_blocks(subtitle_srt_path) if block.text.strip()]
        if not blocks:
            raise RuntimeError("Đã bật tạo giọng đọc tiếng Việt nhưng subtitle Việt rỗng.")
        voiceover = _build_smooth_voiceover_lines(blocks)
        subtitles = _subtitle_lines_from_voiceover(voiceover)
        script = ProductVideoScript(
            hook=voiceover[0].text,
            voiceover=voiceover,
            subtitles=subtitles,
            cta=voiceover[-1].text,
            caption=" ".join(line.text for line in voiceover[:2]),
            hashtags=["#douyin", "#review", "#sanpham"],
        )
        merged_tts_settings = voiceover_tts_settings(
            tts_settings,
            provider=settings.silent_voiceover_provider,
            voice=settings.silent_voiceover_voice,
            language=settings.target_language,
            output_format="mp3",
        )
        voiceover_path = self.voice_generator.generate_voiceover(
            script,
            output_dir,
            filename=f"{Path(output_name).stem}_voiceover.mp3",
            text_filename=f"{Path(output_name).stem}_voiceover_text.txt",
            language=settings.target_language,
            target_duration=target_duration,
            tts_settings=merged_tts_settings,
            allow_script_shortening=False,
            lock_subtitle_timing=False,
        )
        if len(voiceover) < len(blocks):
            self.voice_generator.warnings.append(
                f"voiceover_sentence_grouping: Đã gom {len(blocks)} dòng phụ đề thành {len(voiceover)} cụm đọc "
                "để giọng đọc liền mạch hơn; subtitle hiển thị vẫn giữ timing gốc."
            )
        result = self.voice_generator.last_tts_result
        if not result or result.provider == "silent":
            raise RuntimeError(
                "TTS không tạo được giọng đọc thật. Hãy kiểm tra provider/voice hoặc cấu hình Google Cloud TTS/Piper."
            )
        if not Path(voiceover_path).exists() or Path(voiceover_path).stat().st_size <= 0:
            raise RuntimeError("TTS báo thành công nhưng file voiceover không tồn tại hoặc bị rỗng.")
        return voiceover_path

    def _subtitle_cover_options(
        self,
        *,
        settings: DouyinReupSettings,
        video: DouyinVideoItem,
        source_ocr_debug_path: str | None,
        warnings: list[str],
    ) -> dict:
        height_ratio = settings.subtitle_cover_height_ratio
        bottom_ratio = settings.subtitle_cover_bottom_ratio
        cover_segments: list[dict] = []
        if settings.subtitle_cover_enabled and settings.subtitle_cover_auto_position and source_ocr_debug_path:
            placement = detect_subtitle_cover_from_ocr_debug(
                source_ocr_debug_path,
                fallback_height_ratio=settings.subtitle_cover_height_ratio,
                fallback_bottom_ratio=settings.subtitle_cover_bottom_ratio,
                padding_ratio=settings.subtitle_cover_padding_ratio,
            )
            if placement:
                height_ratio = placement.height_ratio
                bottom_ratio = placement.bottom_ratio
                cover_segments = [asdict(segment) for segment in placement.segments]
                if placement.source == "ocr_debug_bottom_fallback":
                    warnings.append(
                        "subtitle_cover_auto_position_bottom_fallback: OCR vị trí phụ đề Trung bị nhiễu hoặc confidence thấp; "
                        f"đã dùng dải che đáy mỏng ({placement.block_count} vùng gợi ý, confidence {placement.confidence:.2f})."
                    )
                else:
                    warnings.append(
                        "subtitle_cover_auto_position: Đã tự đặt nền phụ đề Việt theo vị trí chữ Trung "
                        f"từ OCR ({placement.block_count} vùng chữ, {len(cover_segments)} mốc thời gian, "
                        f"confidence {placement.confidence:.2f})."
                    )
            else:
                warnings.append(
                    "subtitle_cover_auto_position_fallback: Không đủ tọa độ OCR để tự đặt nền che sub Trung; "
                    "đã dùng vùng che đáy mặc định cho video này."
                )
        return {
            "cover_background_enabled": settings.subtitle_cover_enabled,
            "cover_background_color": settings.subtitle_cover_color,
            "cover_background_opacity": settings.subtitle_cover_opacity,
            "cover_background_height_ratio": height_ratio,
            "cover_background_bottom_ratio": bottom_ratio,
            "cover_background_segments": cover_segments,
            "cover_background_lead_seconds": settings.subtitle_cover_lead_seconds,
            "cover_background_tail_seconds": settings.subtitle_cover_tail_seconds,
            "cover_background_radius_ratio": settings.subtitle_cover_radius_ratio,
            "cover_background_text_y_offset_ratio": settings.subtitle_cover_text_y_offset_ratio,
        }

    def _run_render_with_audio_fallback(
        self,
        *,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        output_path: str,
        width: int,
        height: int,
        overlay_path: str | None,
        subtitle_ass_path: str | None,
        bgm_path: str | None,
        voiceover_path: str | None = None,
        render_duration: float | None = None,
        video_slowdown_factor: float = 1.0,
        subtitle_cover_options: dict | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        try:
            self._run_render(
                video=video,
                settings=settings,
                output_path=output_path,
                width=width,
                height=height,
                overlay_path=overlay_path,
                subtitle_ass_path=subtitle_ass_path,
                bgm_path=bgm_path,
                voiceover_path=voiceover_path,
                render_duration=render_duration,
                video_slowdown_factor=video_slowdown_factor,
                subtitle_cover_options=subtitle_cover_options,
            )
        except FFmpegError:
            if not settings.reduce_original_voice:
                raise
            retry_settings = settings.model_copy(
                update={
                    "reduce_original_voice": False,
                    "original_audio_volume": min(
                        settings.original_audio_volume,
                        settings.original_voice_reduction_fallback_volume,
                    ),
                }
            )
            self._run_render(
                video=video,
                settings=retry_settings,
                output_path=output_path,
                width=width,
                height=height,
                overlay_path=overlay_path,
                subtitle_ass_path=subtitle_ass_path,
                bgm_path=bgm_path,
                voiceover_path=voiceover_path,
                render_duration=render_duration,
                video_slowdown_factor=video_slowdown_factor,
                subtitle_cover_options=subtitle_cover_options,
            )
            if warnings is not None:
                warnings.append(
                    "Giảm giọng Trung bằng bộ lọc center-cancel không chạy ổn với file này; "
                    "đã render lại bằng cách hạ âm lượng audio gốc để giữ batch tiếp tục."
                )

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
        render_duration: float | None = None,
        video_slowdown_factor: float = 1.0,
        subtitle_cover_options: dict | None = None,
    ) -> None:
        duration = max(0.1, float(render_duration or video.duration))
        slowdown = max(1.0, float(video_slowdown_factor or 1.0))
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

        video_chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
        if slowdown > 1.0 + MIN_VIDEO_SLOWDOWN_DELTA:
            video_chain += f",setpts={slowdown:.6f}*PTS"
        video_chain += f",fps={settings.fps},setsar=1[v0]"
        video_filters = [
            video_chain
        ]
        current_label = "[v0]"
        if overlay_input_index is not None:
            video_filters.append(
                f"[{overlay_input_index}:v]format=rgba,scale={width}:{height}[ov];"
                f"{current_label}[ov]overlay=0:0:eof_action=repeat:shortest=0:repeatlast=1[v1]"
            )
            current_label = "[v1]"
        if subtitle_cover_options:
            blur_filter = _build_static_subtitle_cover_blur_filter(
                current_label,
                "vblur",
                width,
                height,
                subtitle_cover_options,
                settings.subtitle_cover_blur_strength,
            )
            if blur_filter:
                video_filters.append(blur_filter)
                current_label = "[vblur]"
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
            duration=duration,
            bgm_input_index=bgm_input_index,
            voice_input_index=voice_input_index,
            video_slowdown_factor=slowdown,
            reduce_original_voice=settings.reduce_original_voice,
            original_voice_reduction_strength=settings.original_voice_reduction_strength,
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
                f"{duration:.3f}",
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
        video_slowdown_factor: float = 1.0,
        reduce_original_voice: bool = False,
        original_voice_reduction_strength: float = 0.65,
    ) -> tuple[str, str | None]:
        filters: list[str] = []
        labels: list[str] = []
        if has_original_audio:
            original_parts: list[str] = []
            if reduce_original_voice:
                strength = max(0.0, min(1.0, float(original_voice_reduction_strength)))
                original_parts.extend(
                    [
                        "aformat=channel_layouts=stereo",
                        f"pan=stereo|c0=c0-{strength:.3f}*c1|c1=c1-{strength:.3f}*c0",
                    ]
                )
            original_parts.append(f"volume={_clamp_volume(original_audio_volume):.3f}")
            slowdown = max(1.0, float(video_slowdown_factor or 1.0))
            if slowdown > 1.0 + MIN_VIDEO_SLOWDOWN_DELTA:
                original_parts.append(VoiceGenerator._atempo_filter(1.0 / slowdown))
                original_parts.append(f"atrim=0:{duration:.3f}")
                original_parts.append("asetpts=PTS-STARTPTS")
            filters.append(f"[0:a]{','.join(original_parts)}[a0]")
            labels.append("[a0]")
        if has_bgm and bgm_input_index is not None:
            fade_out_start = max(0.0, float(duration) - 0.8)
            filters.append(
                f"[{bgm_input_index}:a]volume={_clamp_volume(bgm_volume):.3f},"
                f"afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.3f}:d=0.8[a1]"
            )
            labels.append("[a1]")
        if has_voiceover and voice_input_index is not None:
            filters.append(
                f"[{voice_input_index}:a]volume={VOICEOVER_AUDIO_GAIN:.3f},"
                f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,{AUDIO_LIMITER_FILTER}[av]"
            )
            labels.append("[av]")
        if not labels:
            return "", None
        if len(labels) == 1:
            return (
                ";".join(filters)
                + f";{labels[0]}{MASTER_LOUDNESS_FILTER}[aout]"
            ), "[aout]"
        return (
            ";".join(filters)
            + f";{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,"
            f"{MASTER_LOUDNESS_FILTER}[aout]"
        ), "[aout]"


def _escape_filter_path(path: str) -> str:
    cleaned = str(Path(path).expanduser().resolve()).replace("\\", "/")
    return (
        cleaned.replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )


def _build_static_subtitle_cover_blur_filter(
    input_label: str,
    output_label: str,
    width: int,
    height: int,
    cover_options: dict,
    blur_strength: int,
) -> str | None:
    if width <= 0 or height <= 0:
        return None
    height_ratio = _clamp_float(float(cover_options.get("cover_background_height_ratio") or 0.12), 0.05, 0.45)
    bottom_ratio = _clamp_float(float(cover_options.get("cover_background_bottom_ratio") or 0.0), 0.0, 0.35)
    cover_h = max(2, min(height, int(round(height * height_ratio))))
    cover_bottom = max(cover_h, min(height, height - int(round(height * bottom_ratio))))
    cover_y = max(0, min(height - cover_h, cover_bottom - cover_h))
    radius = max(2, min(int(blur_strength), 30, max(2, cover_h // 2 - 1)))
    base_label = f"{output_label}_base"
    crop_label = f"{output_label}_crop"
    blur_label = f"{output_label}_area"
    return (
        f"{input_label}split=2[{base_label}][{crop_label}];"
        f"[{crop_label}]crop={width}:{cover_h}:0:{cover_y},"
        f"boxblur=luma_radius={radius}:luma_power=1:chroma_radius={radius}:chroma_power=1[{blur_label}];"
        f"[{base_label}][{blur_label}]overlay=0:{cover_y}[{output_label}]"
    )


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _clamp_volume(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _plan_voiceover_video_slowdown(
    blocks: list[SubtitleBlock],
    *,
    settings: DouyinReupSettings,
    target_duration: float,
) -> dict:
    voiceover = _build_smooth_voiceover_lines(blocks)
    reports: list[dict] = []
    required_speeds: list[float] = []
    estimated_total = 0.0
    slot_total = 0.0

    for line in voiceover:
        timing = _parse_voiceover_time_hint(line.time_hint)
        if timing is None:
            continue
        start, end = timing
        slot_duration = max(0.1, end - start)
        estimated_duration = estimate_voice_duration(line.text, settings.target_language)
        if estimated_duration <= 0:
            continue
        required_speed = estimated_duration / slot_duration
        required_speeds.append(required_speed)
        estimated_total += estimated_duration
        slot_total += slot_duration
        reports.append(
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "slot_seconds": round(slot_duration, 3),
                "estimated_voice_seconds": round(estimated_duration, 3),
                "required_speed": round(required_speed, 3),
                "text_chars": len(line.text),
            }
        )

    comfort_speedup = max(1.0, float(settings.voiceover_comfort_speedup))
    max_slowdown = max(1.0, float(settings.voiceover_max_video_slowdown))
    max_required_speed = max(required_speeds) if required_speeds else 1.0
    p90_required_speed = _percentile(required_speeds, 0.9) if required_speeds else 1.0
    slowdown_factor = 1.0
    if settings.voiceover_auto_slow_video and max_required_speed > comfort_speedup:
        pressure_speed = max(p90_required_speed, max_required_speed)
        slowdown_factor = min(max_slowdown, max(1.0, pressure_speed / comfort_speedup))
    if slowdown_factor <= 1.0 + MIN_VIDEO_SLOWDOWN_DELTA:
        slowdown_factor = 1.0

    return {
        "enabled": bool(settings.voiceover_auto_slow_video),
        "line_count": len(reports),
        "source_duration": round(max(0.0, float(target_duration)), 3),
        "scaled_duration": round(max(0.0, float(target_duration)) * slowdown_factor, 3),
        "estimated_voice_seconds": round(estimated_total, 3),
        "source_slot_seconds": round(slot_total, 3),
        "max_required_speed": round(max_required_speed, 3),
        "p90_required_speed": round(p90_required_speed, 3),
        "comfort_speedup": round(comfort_speedup, 3),
        "max_slowdown": round(max_slowdown, 3),
        "slowdown_factor": round(slowdown_factor, 3),
        "lines": reports[:20],
    }


def _parse_voiceover_time_hint(value: str) -> tuple[float, float] | None:
    try:
        start_text, end_text = str(value).rstrip("s").split("-", 1)
        start = float(start_text)
        end = float(end_text)
    except (TypeError, ValueError):
        return None
    if end <= start:
        return None
    return max(0.0, start), max(0.0, end)


def _scale_subtitle_blocks(
    blocks: list[SubtitleBlock],
    *,
    scale: float,
    target_duration: float,
) -> list[SubtitleBlock]:
    scaled: list[SubtitleBlock] = []
    duration = max(0.1, float(target_duration))
    for block in blocks:
        start = min(duration, max(0.0, float(block.start) * scale))
        end = min(duration, max(start + 0.1, float(block.end) * scale))
        if end <= start:
            continue
        scaled.append(
            SubtitleBlock(
                index=len(scaled) + 1,
                start=round(start, 3),
                end=round(end, 3),
                text=block.text,
            )
        )
    return scaled


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, percentile))))
    return ordered[index]


def _build_smooth_voiceover_lines(blocks: list[SubtitleBlock]) -> list[VoiceoverLine]:
    groups: list[VoiceoverLine] = []
    current_texts: list[str] = []
    current_start = 0.0
    current_end = 0.0
    last_accepted_text = ""
    last_accepted_end = 0.0
    recent_accepted: list[tuple[str, float]] = []

    def flush() -> None:
        nonlocal current_texts, current_start, current_end
        text = _join_spoken_texts(current_texts)
        if text:
            groups.append(VoiceoverLine(time_hint=f"{current_start:.2f}-{current_end:.2f}s", text=text))
        current_texts = []

    def remember(text: str, end: float) -> None:
        recent_accepted.append((text, end))
        del recent_accepted[:-5]

    for block in blocks:
        text = _clean_spoken_text(block.text)
        if not text:
            continue
        gap_from_last = max(0.0, float(block.start) - last_accepted_end)
        if _should_skip_repeated_spoken_block(last_accepted_text, text, gap_from_last) or _matches_recent_repeated_block(
            recent_accepted,
            text,
            float(block.start),
        ):
            last_accepted_end = max(last_accepted_end, float(block.end))
            continue
        if current_texts and _should_skip_repeated_spoken_block(
            _join_spoken_texts(current_texts),
            text,
            max(0.0, float(block.start) - current_end),
        ):
            current_end = max(current_end, float(block.end))
            last_accepted_end = max(last_accepted_end, float(block.end))
            continue
        if not current_texts:
            current_texts = [text]
            current_start = float(block.start)
            current_end = float(block.end)
            last_accepted_text = text
            last_accepted_end = float(block.end)
            remember(text, float(block.end))
            continue

        previous_text = _join_spoken_texts(current_texts)
        gap = max(0.0, float(block.start) - current_end)
        span = max(0.0, float(block.end) - current_start)
        combined_len = len(f"{previous_text} {text}".strip())
        if _should_merge_spoken_subtitle_block(previous_text, text, gap, span, combined_len):
            current_texts.append(text)
            current_end = max(current_end, float(block.end))
            last_accepted_text = text
            last_accepted_end = float(block.end)
            remember(text, float(block.end))
            continue

        flush()
        current_texts = [text]
        current_start = float(block.start)
        current_end = float(block.end)
        last_accepted_text = text
        last_accepted_end = float(block.end)
        remember(text, float(block.end))

    flush()
    return groups


def _subtitle_lines_from_voiceover(lines: list[VoiceoverLine]) -> list[SubtitleLine]:
    subtitles: list[SubtitleLine] = []
    for line in lines:
        try:
            start_text, end_text = line.time_hint.rstrip("s").split("-", 1)
            start = float(start_text)
            end = float(end_text)
        except (ValueError, AttributeError):
            start = None
            end = None
        subtitles.append(SubtitleLine(start_hint=start, end_hint=end, text=line.text))
    return subtitles


def _should_skip_repeated_spoken_block(previous_text: str, next_text: str, gap: float) -> bool:
    if not previous_text or not next_text or gap > 2.8:
        return False
    previous = _normalize_spoken_for_compare(previous_text)
    current = _normalize_spoken_for_compare(next_text)
    if not previous or not current:
        return False
    if previous == current:
        return True
    if min(len(previous), len(current)) >= 10 and (previous in current or current in previous):
        return True
    return SequenceMatcher(None, previous, current).ratio() >= 0.9


def _matches_recent_repeated_block(recent: list[tuple[str, float]], next_text: str, start: float) -> bool:
    for previous_text, previous_end in reversed(recent):
        gap = max(0.0, float(start) - float(previous_end))
        if _should_skip_repeated_spoken_block(previous_text, next_text, gap):
            return True
    return False


def _normalize_spoken_for_compare(text: str) -> str:
    return "".join(ch.lower() for ch in _clean_spoken_text(text) if ch.isalnum())


def _should_merge_spoken_subtitle_block(
    previous_text: str,
    next_text: str,
    gap: float,
    span: float,
    combined_len: int,
) -> bool:
    if gap > 0.65 or span > 8.0 or combined_len > 180:
        return False
    if _ends_soft_clause(previous_text):
        return True
    if _starts_spoken_continuation(next_text):
        return True
    if _ends_sentence(previous_text):
        return False
    if _starts_new_sentence(next_text):
        return False
    return len(previous_text) < 34


def _clean_spoken_text(text: str) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split()).strip()


def _join_spoken_texts(texts: list[str]) -> str:
    joined = ""
    for raw_text in texts:
        text = _clean_spoken_text(raw_text)
        if not text:
            continue
        if joined and _should_insert_sentence_stop(joined, text):
            joined = _ensure_sentence_stop(joined)
        joined = f"{joined} {text}".strip() if joined else text
    return _ensure_sentence_stop(joined)


def _should_insert_sentence_stop(previous_text: str, next_text: str) -> bool:
    if not previous_text or not next_text:
        return False
    if _ends_sentence(previous_text) or _ends_soft_clause(previous_text):
        return False
    return _starts_new_sentence(next_text) and not _starts_spoken_continuation(next_text)


def _ensure_sentence_stop(text: str) -> str:
    cleaned = _clean_spoken_text(text)
    if not cleaned:
        return ""
    if _ends_sentence(cleaned):
        return cleaned
    cleaned = re.sub(r"[\s,;:\-\u2013\u2014\u3001\uff0c\uff1b\uff1a]+$", "", cleaned).rstrip()
    return f"{cleaned}." if cleaned else ""


def _starts_spoken_continuation(text: str) -> bool:
    stripped = _clean_spoken_text(text)
    if not stripped:
        return False
    first = stripped[:1]
    if first and first.islower():
        return True
    head = stripped.split(maxsplit=1)[0].strip(".,;:!?").casefold()
    return head in {
        "and",
        "but",
        "or",
        "so",
        "then",
        "v\u00e0",
        "nh\u01b0ng",
        "n\u00ean",
        "th\u00ec",
        "\u0111\u1ec3",
        "khi",
        "n\u1ebfu",
        "m\u00e0",
        "ho\u1eb7c",
        "hay",
        "r\u1ed3i",
        "gi\u00fap",
        "cho",
        "c\u1ee7a",
        "v\u1edbi",
    }


def _starts_new_sentence(text: str) -> bool:
    stripped = _clean_spoken_text(text).lstrip("\"'([{ ")
    for char in stripped:
        if char.isalnum():
            return char.isupper() or char.isdigit()
        if not char.isspace():
            continue
    return False


def _ends_soft_clause(text: str) -> bool:
    return text.rstrip().endswith((",", ";", ":", "-", "\u2013", "\u2014", "\u3001", "\uff0c", "\uff1b", "\uff1a"))


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", "!", "?", "\u2026", "\u3002", "\uff01", "\uff1f"))


def _allow_render_without_subtitle() -> bool:
    return os.getenv("AUTO_TOOL_ALLOW_RENDER_WITHOUT_SUBTITLE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _allow_render_without_bgm() -> bool:
    return os.getenv("AUTO_TOOL_ALLOW_RENDER_WITHOUT_BGM", "0").strip().lower() in {"1", "true", "yes", "on"}
