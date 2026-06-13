from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.adapters.ffmpeg_adapter import probe_media_duration
from app.modules.audio.audio_normalizer import create_silent_audio, normalize_audio_for_render
from app.modules.cache.cache_service import CacheService
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.crop_safety.crop_safety_service import summarize_crop_safety_for_output
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.music_selector.music_selector import MusicSelector
from app.modules.qa_checker.qa_checker import check_output_video
from app.modules.renderer.overlay_renderer import OverlayRenderer
from app.modules.renderer.renderer import Renderer
from app.modules.render_worker.output_log import (
    base_name,
    extend_errors,
    extend_warnings,
    run_step,
    short_message,
    short_messages,
    status_from_log,
)
from app.modules.script_writer.script_writer import ProductVideoScript, ScriptWriter
from app.modules.sese.sese_engine import SESEEngine
from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService, parse_resolution
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import write_json


LogCallback = Callable[[str, str], None]


def render_one_output(
    index: int,
    timeline: Any,
    config: ProjectConfig,
    output_dir: Path,
    renderer: Renderer,
    voice_generator: VoiceGenerator,
    subtitle_generator: SubtitleGenerator,
    music_selector: MusicSelector,
    custom_script: ProductVideoScript | None,
    preview_only: bool,
    log_callback: LogCallback | None,
    script_override: ProductVideoScript | None = None,
    cache_service: CacheService | None = None,
    source_media_filter_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = base_name(index, preview_only)
    final_path = output_dir / f"{name}.mp4"
    visual_path = output_dir / f"{name}_visual.mp4"
    script_path = output_dir / f"{name}_script.json"
    subtitle_path = output_dir / f"{name}_sub.srt"
    subtitle_ass_path = output_dir / f"{name}_sub.ass"
    overlay_asset_path = output_dir / f"{name}_overlay.png"
    voice_path = output_dir / f"{name}_voice.{_voice_extension(config)}"
    normalized_voice_path = output_dir / f"{name}_voice_normalized.wav"
    voice_text_path = output_dir / f"{name}_voice_text.txt"
    timeline_path = output_dir / f"{name}_timeline.json"
    log_path = output_dir / f"{name}_log.json"
    music_path: str | None = None
    started_at = datetime.now().replace(microsecond=0)
    started_seconds = perf_counter()

    output_log: dict[str, Any] = {
        "index": index,
        "status": "failed",
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "duration_seconds": None,
        "steps": [],
        "visual_video": str(visual_path),
        "final_video": str(final_path),
        "script_file": str(script_path),
        "subtitle_file": str(subtitle_path),
        "subtitle_ass_file": str(subtitle_ass_path),
        "overlay_file": str(overlay_asset_path),
        "voice_file": str(voice_path),
        "normalized_voice_file": str(normalized_voice_path),
        "timeline_file": str(timeline_path),
        "timeline_template": getattr(timeline, "template_id", None) or config.timeline.template_id,
        "average_segment_score": _average_segment_score(timeline),
        "source_diversity": _source_diversity(timeline),
        "music_file": None,
        "tts_provider": None,
        "tts_fallback_used": False,
        "voice_duration": None,
        "tts_warning": None,
        "tts": {
            "provider_requested": config.tts.provider,
            "provider_used": None,
            "fallback_used": False,
            "raw_voice_path": str(voice_path),
            "normalized_voice_path": str(normalized_voice_path),
            "voice_duration": None,
            "target_video_duration": config.render.duration,
            "warnings": [],
        },
        "sese": {
            "enabled": getattr(config.render, "sese_enabled", False),
            "applied": False,
            "strategy": "none",
            "original_duration": None,
            "final_duration": None,
            "added_duration": 0.0,
            "warnings": [],
        },
        "subtitle_sync": {
            "subtitle_active_duration": None,
            "subtitle_file": str(subtitle_path),
            "warnings": [],
        },
        "visual_style": {
            "preset_id": config.visual_style.preset_id,
            "overlay_asset": str(overlay_asset_path),
            "subtitle_format": "ass",
            "ass_subtitle_path": str(subtitle_ass_path),
            "fallback_used": False,
            "warnings": [],
        },
        "crop_safety": summarize_crop_safety_for_output(timeline),
        "source_media_filter": dict(source_media_filter_summary or {}),
        "script_safety": None,
        "cache": _timeline_cache_summary(timeline),
        "performance": {},
        "warnings": [],
        "errors": [],
    }

    try:
        run_step(
            output_log,
            "write_timeline_report",
            lambda: write_json(timeline_path, _timeline_report(timeline, config.timeline.template_id)),
        )

        def generate_script() -> ProductVideoScript:
            if custom_script is not None:
                script_result = custom_script
            elif script_override is not None:
                script_result = script_override
            else:
                script_writer = ScriptWriter()
                script_result = script_writer.generate_script(config, output_index=index)
                extend_warnings(output_log, script_writer.warnings)
            script_result = _with_industry_metadata(script_result, config)
            script_result = _guard_script_or_fallback(script_result, config, index, output_log)
            write_json(script_path, script_result.model_dump(mode="json"))
            return script_result

        script = run_step(output_log, "generate_script", generate_script)

        generated_voice_path = run_step(
            output_log,
            "generate_voice",
            lambda: voice_generator.generate_voiceover(
                script,
                str(output_dir),
                filename=voice_path.name,
                text_filename=voice_text_path.name,
                language=config.ai.language,
                target_duration=config.render.duration,
                tts_settings=config.tts,
            ),
        )
        output_log["voice_file"] = generated_voice_path
        output_log["cache"]["tts_cache_hit"] = bool(getattr(voice_generator, "last_cache_hit", False))
        output_log["tts"]["raw_voice_path"] = generated_voice_path
        output_log["caption"] = script.caption
        output_log["hashtags"] = list(script.hashtags)
        output_log["script_variant_id"] = script.variant_style_id
        extend_warnings(output_log, voice_generator.warnings)
        if voice_generator.last_tts_result is not None:
            output_log["tts_provider"] = voice_generator.last_tts_result.provider
            output_log["tts_fallback_used"] = voice_generator.last_tts_result.fallback_used
            output_log["voice_duration"] = voice_generator.last_tts_result.duration or voice_generator.last_voice_duration
            output_log["tts_warning"] = (
                "; ".join(voice_generator.last_tts_result.warnings)
                if voice_generator.last_tts_result.warnings
                else None
            )
            output_log["tts"]["provider_used"] = voice_generator.last_tts_result.provider
            output_log["tts"]["fallback_used"] = voice_generator.last_tts_result.fallback_used
            output_log["tts"]["warnings"] = list(voice_generator.last_tts_result.warnings)
        synced_subtitles = voice_generator.last_subtitle_timeline

        normalized_voice_for_render, normalized_voice_duration = run_step(
            output_log,
            "normalize_voice",
            lambda: _normalize_voice_for_render(
                raw_voice_path=generated_voice_path,
                normalized_voice_path=str(normalized_voice_path),
                target_duration=config.render.duration,
                output_log=output_log,
            ),
        )
        output_log["normalized_voice_file"] = normalized_voice_for_render
        output_log["voice_duration"] = normalized_voice_duration
        output_log["tts"]["normalized_voice_path"] = normalized_voice_for_render
        output_log["tts"]["voice_duration"] = normalized_voice_duration

        # ── SESE: Adjust timeline ending if voice is longer than visual ──
        sese_enabled = getattr(config.render, "sese_enabled", False) and not preview_only
        sese_timeline = timeline
        if sese_enabled:
            sese_timeline = run_step(
                output_log,
                "sese_synchronize",
                lambda: SESEEngine.synchronize(
                    timeline=timeline,
                    voice_duration=normalized_voice_duration,
                    config=config,
                ),
            )
            sese_meta = getattr(sese_timeline, "sese_metadata", {})
            output_log["sese"].update({
                "applied": sese_meta.get("applied", False),
                "strategy": sese_meta.get("strategy", "none"),
                "original_duration": sese_meta.get("original_duration"),
                "final_duration": sese_meta.get("final_duration"),
                "added_duration": sese_meta.get("added_duration", 0.0),
                "warnings": list(sese_meta.get("warnings", [])),
            })
            if sese_meta.get("warnings"):
                extend_warnings(output_log, sese_meta["warnings"])

        # Determine effective video duration for QA (may be extended by SESE)
        effective_duration = float(
            getattr(sese_timeline, "target_duration", None) or config.render.duration
        )

        rendered_visual_path = run_step(
            output_log,
            "render_visual",
            lambda: renderer.render_timeline(sese_timeline, config, str(output_dir), base_name=name),
        )

        def generate_subtitles() -> str:
            subtitle_generator.generate_srt(
                script,
                config.render.duration,
                voice_duration=normalized_voice_duration,
                output_path=str(subtitle_path),
                subtitle_lines=synced_subtitles,
            )
            try:
                width, height = parse_resolution(config.render.resolution)
                preset = VisualStyleService().resolve_preset(config.visual_style)
                styled_lines = synced_subtitles or script.subtitles
                generate_ass_subtitle(styled_lines, preset, width, height, str(subtitle_ass_path))
                output_log["visual_style"]["preset_id"] = preset.id
            except Exception as exc:
                warning = f"ass_subtitle_failed_fallback_to_srt: Không tạo được phụ đề ASS theo style, dùng ASS mặc định. Lý do: {exc}"
                extend_warnings(output_log, [warning])
                output_log["visual_style"]["fallback_used"] = True
                output_log["visual_style"]["warnings"].append("ass_subtitle_failed_fallback_to_srt")
                subtitle_generator.generate_ass(
                    script,
                    config.render.duration,
                    str(subtitle_ass_path),
                    font_size=config.effects.subtitle_size,
                    overlay_height=config.effects.overlay_height,
                    subtitle_lines=synced_subtitles,
                    voice_duration=normalized_voice_duration,
                )
            output_log["subtitle_sync"]["subtitle_active_duration"] = subtitle_generator.last_active_duration
            output_log["subtitle_sync"]["warnings"] = list(subtitle_generator.warnings)
            extend_warnings(output_log, subtitle_generator.warnings)
            return str(subtitle_path)

        run_step(output_log, "generate_subtitle", generate_subtitles)

        music_path = run_step(output_log, "select_music", lambda: music_selector.select_music(config, index))
        extend_warnings(output_log, music_selector.warnings)
        output_log["music_file"] = music_path

        overlay_renderer = OverlayRenderer(
            cache_service=cache_service,
            cache_enabled=config.cache.cache_overlay_assets,
        )
        output_path = run_step(
            output_log,
            "render_final",
            lambda: overlay_renderer.render_final_video(
                visual_video_path=rendered_visual_path,
                voice_path=normalized_voice_for_render,
                subtitle_path=str(subtitle_ass_path),
                script=script,
                config=config,
                output_path=str(final_path),
                music_path=music_path,
                fallback_subtitle_path=str(subtitle_path),
            ),
        )
        extend_warnings(output_log, overlay_renderer.warnings)
        output_log["cache"]["overlay_cache_hit"] = bool(overlay_renderer.last_overlay_cache_hit)
        if overlay_renderer.last_visual_style:
            output_log["visual_style"] = overlay_renderer.last_visual_style
            output_log["overlay_file"] = overlay_renderer.last_visual_style.get("overlay_asset")

        qa_result = run_step(
            output_log,
            "qa_check",
            lambda: check_output_video(
                output_path,
                effective_duration,
                expected_resolution=config.render.resolution,
                subtitle_path=str(subtitle_path),
                script_path=str(script_path),
            ),
        )
        extend_warnings(output_log, qa_result.get("warnings", []))
        extend_errors(output_log, qa_result.get("errors", []))

        status = status_from_log(output_log)
        output_log["status"] = status
        output_log["qa"] = qa_result
        output_record: dict[str, Any] = {
            "index": index,
            "path": output_path,
            "status": status,
            "duration": qa_result.get("duration"),
            "visual_video": rendered_visual_path,
            "script_file": str(script_path),
            "subtitle_file": str(subtitle_path),
            "subtitle_ass_file": str(subtitle_ass_path),
            "overlay_file": output_log.get("overlay_file"),
            "voice_file": generated_voice_path,
            "normalized_voice_file": normalized_voice_for_render,
            "tts_provider": output_log["tts_provider"],
            "tts_fallback_used": output_log["tts_fallback_used"],
            "timeline_template": output_log["timeline_template"],
            "script_variant_id": script.variant_style_id,
            "caption": script.caption,
            "hashtags": list(script.hashtags),
            "timeline_file": str(timeline_path),
            "music_file": music_path,
            "log_file": str(log_path),
            "visual_style": dict(output_log.get("visual_style", {})),
            "crop_safety": dict(output_log.get("crop_safety", {})),
            "source_media_filter": dict(output_log.get("source_media_filter", {})),
            "script_safety": output_log.get("script_safety"),
            "cache": dict(output_log.get("cache", {})),
            "warnings": short_messages(output_log["warnings"]),
            "errors": short_messages(output_log["errors"]),
            "performance": dict(output_log.get("performance", {})),
        }
        if status == "failed":
            output_record["error"] = short_message(
                output_log["errors"][0] if output_log["errors"] else "QA check failed"
            )
            output_record["qa"] = qa_result
            output_log["error"] = output_log["errors"][0] if output_log["errors"] else output_record["error"]
        return output_record
    except Exception as exc:
        message = f"Render failed for output {index:03d}: {exc}"
        if log_callback:
            log_callback("error", short_message(message))
        extend_errors(output_log, [message])
        output_log["error"] = message
        output_log["status"] = "failed"
        return {
            "index": index,
            "path": str(final_path),
            "status": "failed",
            "duration": None,
            "error": short_message(message),
            "warnings": short_messages(output_log["warnings"]),
            "errors": short_messages(output_log["errors"]),
            "visual_video": str(visual_path),
            "script_file": str(script_path),
            "subtitle_file": str(subtitle_path),
            "subtitle_ass_file": str(subtitle_ass_path),
            "overlay_file": output_log.get("overlay_file"),
            "voice_file": str(voice_path),
            "normalized_voice_file": str(normalized_voice_path),
            "timeline_file": str(timeline_path),
            "music_file": music_path,
            "log_file": str(log_path),
            "visual_style": dict(output_log.get("visual_style", {})),
            "crop_safety": dict(output_log.get("crop_safety", {})),
            "source_media_filter": dict(output_log.get("source_media_filter", {})),
            "script_safety": output_log.get("script_safety"),
            "cache": dict(output_log.get("cache", {})),
            "performance": dict(output_log.get("performance", {})),
        }
    finally:
        finished_at = datetime.now().replace(microsecond=0)
        output_log["finished_at"] = finished_at.isoformat()
        output_log["duration_seconds"] = round(perf_counter() - started_seconds, 3)
        output_log["performance"]["total_seconds"] = output_log["duration_seconds"]
        write_json(log_path, output_log)


def _timeline_report(timeline: Any, fallback_template_id: str) -> dict[str, Any]:
    clips = [clip.model_dump(mode="json") for clip in timeline.clips]
    return {
        "output_index": timeline.output_index,
        "template_id": getattr(timeline, "template_id", None) or fallback_template_id,
        "target_duration": timeline.target_duration,
        "average_segment_score": _average_segment_score(timeline),
        "source_diversity": _source_diversity(timeline),
        "clips": clips,
    }


def _timeline_cache_summary(timeline: Any) -> dict[str, Any]:
    clips = list(getattr(timeline, "clips", []) or [])
    return {
        "segment_score_cache_hits": sum(1 for clip in clips if getattr(clip, "segment_score_cache_hit", False)),
        "crop_safety_cache_hits": sum(1 for clip in clips if getattr(clip, "crop_cache_hit", False)),
        "tts_cache_hit": False,
        "overlay_cache_hit": False,
    }


def _average_segment_score(timeline: Any) -> float:
    scores = [clip.segment_score for clip in timeline.clips if clip.segment_score is not None]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 3)


def _source_diversity(timeline: Any) -> dict[str, int]:
    sources = [clip.source_path for clip in timeline.clips]
    return {
        "unique_sources": len(set(sources)),
        "total_clips": len(sources),
    }


def _voice_extension(config: ProjectConfig) -> str:
    provider = config.tts.provider.strip().lower().replace("-", "_")
    output_format = config.tts.output_format.strip().lower().lstrip(".")
    if provider == "piper":
        return "wav"
    if output_format in {"mp3", "wav"}:
        return output_format
    return "mp3"


def _normalize_voice_for_render(
    raw_voice_path: str,
    normalized_voice_path: str,
    target_duration: float,
    output_log: dict[str, Any],
) -> tuple[str, float]:
    try:
        normalized_path = normalize_audio_for_render(
            raw_voice_path,
            normalized_voice_path,
            target_format="wav",
            sample_rate=44100,
        )
    except Exception as exc:
        warning = f"voice_normalization_failed: Không thể chuẩn hoá giọng đọc, đang dùng âm thanh im lặng dự phòng. Lý do: {exc}"
        extend_warnings(output_log, [warning])
        output_log["tts"]["warnings"].append(warning)
        normalized_path = create_silent_audio(normalized_voice_path, duration=target_duration, sample_rate=44100)

    duration = round(probe_media_duration(normalized_path), 3)
    return normalized_path, duration


def _guard_script_or_fallback(
    script: ProductVideoScript,
    config: ProjectConfig,
    index: int,
    output_log: dict[str, Any],
) -> ProductVideoScript:
    service = SafetyGuardService()
    result = service.check_script_output(script, config.product, target_duration=config.render.duration)
    output_log["script_safety"] = {
        "passed": result.passed,
        "warnings_count": result.warnings_count,
        "errors_count": result.errors_count,
        "issues": [issue.model_dump(mode="json") for issue in result.issues],
        "fallback_used": False,
    }
    extend_warnings(output_log, [issue.message for issue in result.issues if issue.severity == "warning"])
    if not result.errors_count:
        return script

    extend_warnings(
        output_log,
        [
            "script_safety_failed_fallback: Script generated không an toàn, đang dùng fallback script.",
            *[issue.message for issue in result.issues if issue.severity == "error"],
        ],
    )
    fallback = _with_industry_metadata(_fallback_script_for_config(config, index), config)
    fallback_result = service.check_script_output(fallback, config.product, target_duration=config.render.duration)
    output_log["script_safety"] = {
        "passed": fallback_result.passed,
        "warnings_count": fallback_result.warnings_count,
        "errors_count": fallback_result.errors_count,
        "issues": [issue.model_dump(mode="json") for issue in fallback_result.issues],
        "original_issues": [issue.model_dump(mode="json") for issue in result.issues],
        "fallback_used": True,
    }
    extend_warnings(output_log, [issue.message for issue in fallback_result.issues if issue.severity == "warning"])
    if fallback_result.errors_count:
        raise ValueError(
            "Fallback script safety check failed: "
            + "; ".join(issue.message for issue in fallback_result.issues if issue.severity == "error")
        )
    return fallback


def _fallback_script_for_config(config: ProjectConfig, index: int) -> ProductVideoScript:
    industry = None
    if config.industry and config.industry.preset_id:
        industry = IndustryPresetService().get_preset(config.industry.preset_id)
    return ScriptWriter._fallback_script(config, index, industry)


def _with_industry_metadata(script: ProductVideoScript, config: ProjectConfig) -> ProductVideoScript:
    if not config.industry or not config.industry.preset_id:
        return script
    preset = IndustryPresetService().get_preset(config.industry.preset_id)
    return script.model_copy(
        update={
            "industry_preset_id": script.industry_preset_id or preset.id,
            "caption_tone": script.caption_tone or preset.caption_tone,
            "hashtag_suggestions_used": list(script.hashtag_suggestions_used)
            or list(preset.hashtag_suggestions),
            "hashtags": list(script.hashtags) or list(preset.hashtag_suggestions[:6]),
        }
    )
