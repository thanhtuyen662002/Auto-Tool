from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.cache.cache_service import CacheService
from app.modules.crop_safety.crop_safety_service import CropSafetyService
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.music_selector.music_selector import MusicSelector
from app.modules.renderer.renderer import Renderer
from app.modules.render_worker.output_pipeline import render_one_output
from app.modules.render_worker.summary_builder import failed_output_records, finalize_summary
from app.modules.performance.performance_timer import performance_summary
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.segmenter.segmenter import Segmenter
from app.modules.source_media_manager.media_filter_service import (
    MediaFilterService,
    source_media_summary_for_filter,
    summarize_timeline_source_filter,
)
from app.modules.subtitle_generator.subtitle_generator import SubtitleGenerator
from app.modules.timeline_templates.product_timeline_builder import ProductTimelineBuilder
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json


ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str, str], None]


def render_project(
    config: ProjectConfig,
    preview_only: bool = False,
    custom_script: ProductVideoScript | None = None,
    project_id: str | None = None,
    progress_callback: ProgressCallback | None = None,
    log_callback: LogCallback | None = None,
) -> dict[str, Any]:
    from time import perf_counter
    _render_started = perf_counter()
    created_at = datetime.now().replace(microsecond=0)
    working_config = _preview_config(config) if preview_only else config
    active_project_id = project_id or working_config.project_name
    output_dir = _make_output_dir(working_config, created_at, preview_only)
    cache_service = CacheService.for_project(working_config, log_callback=log_callback)
    if working_config.cache.clear_cache_before_render:
        cache_service.clear()
        _log(log_callback, "info", "Đã xoá cache dự án trước khi render.")
    safety_result = SafetyGuardService().check_before_render(working_config)

    outputs: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "project_name": working_config.project_name,
        "created_at": created_at.isoformat(),
        "source_folder": working_config.source_folder,
        "output_folder": str(output_dir),
        "total_input_videos": 0,
        "total_segments": 0,
        "requested_outputs": working_config.render.output_count,
        "total_outputs": working_config.render.output_count,
        "successful_outputs": 0,
        "failed_outputs": 0,
        "warnings_count": 0,
        "failed_items": [],
        "industry_preset": _industry_summary(working_config),
        "safety_check": safety_result.model_dump(mode="json"),
        "source_media_summary": None,
        "cache_summary": cache_service.summary(),
        "outputs": outputs,
    }

    _log(log_callback, "info", f"Thư mục đầu ra: {output_dir}")
    for issue in safety_result.issues:
        if issue.severity == "warning":
            _log(log_callback, "warning", f"Safety check: {issue.message}")
    _progress(
        progress_callback,
        current_step="scanning_media",
        progress=5,
        total_outputs=working_config.render.output_count,
        completed_outputs=0,
        failed_outputs=0,
    )

    try:
        if safety_result.errors_count:
            raise ValueError(
                "Product info safety check failed: "
                + "; ".join(issue.message for issue in safety_result.issues if issue.severity == "error")
            )
        media_files = MediaScanner(
            cache_service=cache_service,
            cache_enabled=working_config.cache.cache_media_metadata,
        ).scan_folder(working_config.source_folder)
        summary["total_input_videos"] = len(media_files)
        _log(log_callback, "info", f"Tìm thấy {len(media_files)} video nguồn hợp lệ")
        if not media_files:
            raise ValueError(f"Không tìm thấy video nguồn hợp lệ trong {working_config.source_folder}")

        _progress(
            progress_callback,
            current_step="creating_segments",
            progress=15,
            total_outputs=working_config.render.output_count,
            completed_outputs=0,
            failed_outputs=0,
        )
        segments = Segmenter().create_segments(media_files, working_config.effects.cut_intensity)
        summary["total_segments"] = len(segments)
        _log(log_callback, "info", f"Đã tạo {len(segments)} cảnh cắt")
        if not segments:
            raise ValueError("Không tạo được cảnh cắt nào dùng được từ video nguồn.")

        _progress(
            progress_callback,
            current_step="scoring_segments",
            progress=20,
            total_outputs=working_config.render.output_count,
            completed_outputs=0,
            failed_outputs=0,
        )
        scored_segments = SegmentScorer(
            cache_service=cache_service,
            cache_enabled=working_config.cache.cache_segment_scoring,
            settings_hash=cache_service.settings_hash(
                {
                    "scorer": "segment_scorer_v1",
                    "max_frames": 5,
                    "resolution": working_config.render.resolution,
                }
            ),
        ).score_segments(segments)
        scoring_report = build_scoring_report(scored_segments)
        scoring_report_path = output_dir / "segment_scoring_report.json"
        write_json(scoring_report_path, scoring_report)
        summary["segment_scoring"] = scoring_report
        summary["segment_scoring_report"] = str(scoring_report_path)
        _log(
            log_callback,
            "info",
            "Đã chấm điểm cảnh: "
            f"{scoring_report['usable_segments']} dùng được, "
            f"{scoring_report['rejected_segments']} bị loại, "
            f"điểm trung bình={scoring_report['average_score']}",
        )
        media_filter = MediaFilterService(log_callback=log_callback)
        filtered_segments = media_filter.filter_segments_for_render(
            active_project_id,
            scored_segments,
            config=working_config,
        )
        summary["source_media_summary"] = source_media_summary_for_filter(
            media_filter.last_summary,
            total_media=len(media_files),
        )
        _log(
            log_callback,
            "info",
            "Source media filter: "
            f"{media_filter.last_summary.get('segments_before_filter', 0)} -> "
            f"{media_filter.last_summary.get('segments_after_filter', 0)} segments",
        )

        timeline_segments = _select_timeline_segments(
            filtered_segments,
            working_config.render.output_count,
            log_callback,
        )

        _progress(
            progress_callback,
            current_step="building_timelines",
            progress=25,
            total_outputs=working_config.render.output_count,
            completed_outputs=0,
            failed_outputs=0,
        )
        template_id = working_config.timeline.template_id
        _log(log_callback, "info", f"Đang dựng dòng thời gian theo sản phẩm với mẫu: {template_id}")
        timelines = ProductTimelineBuilder().build_timelines(
            segments=timeline_segments,
            output_count=working_config.render.output_count,
            target_duration=working_config.render.duration,
            template_id=template_id,
            speed_variation=working_config.effects.speed_variation,
        )
        if isinstance(summary.get("source_media_summary"), dict):
            summary["source_media_summary"]["favorite_segments_used"] = sum(
                1
                for timeline in timelines
                for clip in timeline.clips
                if clip.user_review_status == "favorite"
            )
        _log(log_callback, "info", f"Đã dựng {len(timelines)} dòng thời gian")
        crop_report = CropSafetyService(
            cache_service=cache_service,
            cache_enabled=working_config.cache.cache_crop_safety,
        ).analyze_timelines(
            timelines=timelines,
            config=working_config,
            output_dir=output_dir,
        )
        summary["crop_safety"] = crop_report.model_dump(mode="json")
        _log(
            log_callback,
            "info",
            "Crop safety: "
            f"average={crop_report.average_crop_safety_score}, "
            f"blur_fallback={crop_report.fallback_to_blur_background}, "
            f"warnings={sum(crop_report.warnings_summary.values())}",
        )

        renderer = Renderer()
        voice_generator = VoiceGenerator(
            cache_service=cache_service,
            cache_enabled=working_config.cache.cache_tts,
        )
        subtitle_generator = SubtitleGenerator()
        music_selector = MusicSelector()
        script_variants = _generate_script_variants_if_needed(
            working_config,
            output_dir,
            custom_script,
            cache_service,
            log_callback,
        )
        if script_variants:
            summary["script_variants_file"] = str(output_dir / "script_variants.json")

        for timeline in timelines:
            index = timeline.output_index
            completed_outputs = sum(1 for item in outputs if item["status"] in {"success", "warning"})
            failed_outputs = sum(1 for item in outputs if item["status"] == "failed")
            base_progress = 30 + int(((index - 1) / max(1, len(timelines))) * 65)
            _progress(
                progress_callback,
                current_step=f"rendering_video_{index}",
                progress=base_progress,
                total_outputs=len(timelines),
                completed_outputs=completed_outputs,
                failed_outputs=failed_outputs,
            )
            _log(log_callback, "info", f"Đang render video {index:03d}")

            outputs.append(
                render_one_output(
                    index=index,
                    timeline=timeline,
                    config=working_config,
                    output_dir=output_dir,
                    renderer=renderer,
                    voice_generator=voice_generator,
                    subtitle_generator=subtitle_generator,
                    music_selector=music_selector,
                    custom_script=custom_script,
                    script_override=_script_for_output(index, custom_script, script_variants),
                    preview_only=preview_only,
                    log_callback=log_callback,
                    cache_service=cache_service,
                    source_media_filter_summary=summarize_timeline_source_filter(
                        timeline,
                        media_filter.last_summary,
                    ),
                )
            )

        finalize_summary(summary)
    except Exception as exc:
        outputs.extend(
            failed_output_records(
                config=working_config,
                output_dir=output_dir,
                preview_only=preview_only,
                reason=str(exc),
                start_index=len(outputs) + 1,
            )
        )
        finalize_summary(summary)
        summary["error"] = str(exc)
        _log(log_callback, "error", str(exc))
    finally:
        finalize_summary(summary)
        summary["cache_summary"] = cache_service.summary()
        # Build performance_summary before writing
        from time import perf_counter as _pc
        total_runtime = round(_pc() - _render_started, 3)
        summary["performance_summary"] = performance_summary(
            summary.get("outputs", []),
            total_runtime,
            cache_summary=summary.get("cache_summary"),
        )
        summary_path = output_dir / "project_summary.json"
        write_json(summary_path, summary)
        _log(log_callback, "info", f"Đã ghi tổng kết dự án: {summary_path}")

    _progress(
        progress_callback,
        current_step="completed",
        progress=100,
        total_outputs=working_config.render.output_count,
        completed_outputs=summary["successful_outputs"],
        failed_outputs=summary["failed_outputs"],
    )
    return summary


def _preview_config(config: ProjectConfig) -> ProjectConfig:
    render = config.render.model_copy(
        update={
            "output_count": 1,
            "duration": min(config.render.duration, 8.0),
        }
    )
    return config.model_copy(update={"render": render})


def _make_output_dir(config: ProjectConfig, created_at: datetime, preview_only: bool) -> Path:
    if preview_only:
        return ensure_dir(Path(config.output_folder) / "preview")
    return ensure_dir(Path(config.output_folder) / f"{config.project_name}-{created_at.strftime('%Y-%m-%d-%H%M%S')}")


def _select_timeline_segments(segments: list, output_count: int, log_callback: LogCallback | None) -> list:
    usable_segments = [
        segment
        for segment in segments
        if segment.score_detail is not None and not segment.score_detail.is_rejected
    ]
    favorite_segments = [
        segment
        for segment in segments
        if getattr(segment, "user_review_status", None) == "favorite"
    ]
    low_quality_favorites = [
        segment
        for segment in favorite_segments
        if segment.score_detail is not None and segment.score_detail.is_rejected
    ]
    if low_quality_favorites:
        _log(log_callback, "warning", "favorite_segment_has_low_quality_score")
    if favorite_segments:
        merged = {
            (segment.id, segment.source_path, segment.start, segment.end): segment
            for segment in [*favorite_segments, *usable_segments]
        }
        usable_segments = list(merged.values())
    if not usable_segments:
        raise ValueError("Không còn cảnh cắt dùng được sau bước chấm điểm.")

    minimum_segments = max(3, output_count)
    if len(usable_segments) >= minimum_segments:
        return usable_segments

    rejected_by_score = sorted(
        [segment for segment in segments if segment not in usable_segments],
        key=lambda segment: segment.score,
        reverse=True,
    )
    supplemented = (usable_segments + rejected_by_score)[: max(minimum_segments, len(usable_segments))]
    _log(
        log_callback,
        "warning",
        "Có quá ít cảnh chất lượng cao sau bước chấm điểm; đang dùng thêm cảnh dự phòng "
        f"({len(usable_segments)} dùng được, {len(supplemented)} tổng số cho dòng thời gian).",
    )
    return supplemented


def _generate_script_variants_if_needed(
    config: ProjectConfig,
    output_dir: Path,
    custom_script: ProductVideoScript | None,
    cache_service: CacheService,
    log_callback: LogCallback | None,
) -> list[ProductVideoScript] | None:
    if custom_script is not None:
        _log(log_callback, "info", "Đang dùng kịch bản tuỳ chỉnh của dự án; bỏ qua biến thể kịch bản.")
        return None

    cache_key = _script_variants_cache_key(config, cache_service)
    if cache_key:
        cached = cache_service.get_json("scripts", cache_key)
        if cached:
            try:
                scripts = [ProductVideoScript.model_validate(item) for item in cached.get("scripts", [])]
                if len(scripts) == config.render.output_count:
                    write_json(
                        output_dir / "script_variants.json",
                        {
                            "project_name": config.project_name,
                            "timeline_template_id": config.timeline.template_id,
                            "total_variants": len(scripts),
                            "cached": True,
                            "variants": [script.model_dump(mode="json") for script in scripts],
                        },
                    )
                    _log(log_callback, "info", "Đã dùng lại cache biến thể kịch bản.")
                    return scripts
            except Exception as exc:
                _log(log_callback, "warning", f"Không thể đọc cache biến thể kịch bản, sẽ tạo lại: {exc}")

    generator = ScriptVariantGenerator()
    variants = generator.generate_variants(
        config=config,
        output_count=config.render.output_count,
        timeline_template_id=config.timeline.template_id,
    )
    report_path = generator.write_report(output_dir, config)
    for warning in generator.warnings:
        _log(log_callback, "warning", warning)
    for index, script in enumerate(variants, start=1):
        style = script.variant_style_id or "unknown"
        _log(log_callback, "info", f"Biến thể kịch bản cho video {index:03d}: {style}")
    _log(log_callback, "info", f"Đã ghi file biến thể kịch bản: {report_path}")
    if cache_key:
        cache_service.set_json(
            cache_key,
            {
                "project_name": config.project_name,
                "timeline_template_id": config.timeline.template_id,
                "output_count": config.render.output_count,
                "scripts": [script.model_dump(mode="json") for script in variants],
            },
        )
    return variants


def _script_variants_cache_key(config: ProjectConfig, cache_service: CacheService) -> str | None:
    if not cache_service.enabled:
        return None
    payload = {
        "project_name": config.project_name,
        "product": config.product.model_dump(mode="json"),
        "render_duration": config.render.duration,
        "output_count": config.render.output_count,
        "timeline_template_id": config.timeline.template_id,
        "script_variation": config.script_variation.model_dump(mode="json"),
        "ai": {
            "text_model": config.ai.text_model,
            "tone": config.ai.tone,
            "language": config.ai.language,
        },
        "industry": config.industry.model_dump(mode="json") if config.industry else None,
    }
    return f"scripts/{cache_service.settings_hash(payload)}"


def _script_for_output(
    index: int,
    custom_script: ProductVideoScript | None,
    script_variants: list[ProductVideoScript] | None,
) -> ProductVideoScript | None:
    if custom_script is not None:
        return custom_script
    if not script_variants:
        return None
    try:
        return script_variants[index - 1]
    except IndexError as exc:
        raise ValueError(f"Thiếu biến thể kịch bản cho video {index:03d}") from exc


def _industry_summary(config: ProjectConfig) -> dict[str, Any] | None:
    if not config.industry or not config.industry.preset_id:
        return None
    preset = IndustryPresetService().get_preset(config.industry.preset_id)
    return {
        "preset_id": preset.id,
        "name": preset.name,
        "timeline_template_id": preset.timeline_template_id,
        "visual_style_preset_id": preset.visual_style_preset_id,
        "caption_tone": preset.caption_tone,
    }


def _progress(callback: ProgressCallback | None, **payload: Any) -> None:
    if callback:
        callback(payload)


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)
