from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
import gc
import threading
import time
from typing import Any

from app.adapters.ffmpeg_adapter import ffmpeg_timeout
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
from app.modules.queue_control import (
    QueueControlService,
    QueueItemPriority,
    QueueItemStatus,
    QueueRunStatus,
    QueueSettings,
    QueueState,
    QueueStateService,
    ResourceGuardService,
    StageGate,
)
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
    job_id: str | None = None,
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
        "product_assets": _product_assets_summary(working_config),
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

        queue_state_service: QueueStateService | None = None
        queue_control: QueueControlService | None = None
        resource_guard: ResourceGuardService | None = None
        queue_state: QueueState | None = None
        if job_id:
            queue_state_service = QueueStateService()
            queue_control = QueueControlService(queue_state_service)
            queue_state = queue_state_service.load_queue_state(job_id)
            if queue_state is None:
                queue_state = queue_state_service.create_queue_state(
                    job_id=job_id,
                    mode="product_render",
                    video_paths=_timeline_queue_paths(timelines),
                    settings=_queue_settings_for_product_render(working_config, preview_only),
                    output_dir=str(output_dir),
                    project_id=active_project_id,
                )
            resource_guard = ResourceGuardService(str(output_dir))

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

        timeline_by_video_id = {f"video_{timeline.output_index:03d}": timeline for timeline in timelines}
        parallel_queue_enabled = bool(
            queue_state_service
            and queue_control
            and job_id
            and queue_state
            and _queue_worker_pool_enabled(queue_state)
        )
        if parallel_queue_enabled and queue_state_service and queue_control and job_id and queue_state:
            outputs.extend(
                _render_product_queue_parallel(
                    timelines=timelines,
                    timeline_by_video_id=timeline_by_video_id,
                    config=working_config,
                    output_dir=output_dir,
                    custom_script=custom_script,
                    script_variants=script_variants,
                    preview_only=preview_only,
                    job_id=job_id,
                    queue_state=queue_state,
                    queue_state_service=queue_state_service,
                    queue_control=queue_control,
                    resource_guard=resource_guard,
                    source_filter_summary=media_filter.last_summary,
                    progress_callback=progress_callback,
                    log_callback=log_callback,
                )
            )
            if queue_control.should_cancel(job_id):
                summary["queue_status"] = "cancelled"
            elif queue_control.should_pause(job_id):
                summary["queue_status"] = "paused"

        while not parallel_queue_enabled:
            queue_item = None
            if queue_state_service and job_id:
                queue_state = queue_state_service.load_queue_state(job_id) or queue_state
                if queue_control and queue_control.should_cancel(job_id):
                    queue_control.mark_cancelled(job_id)
                    summary["queue_status"] = "cancelled"
                    break
                if queue_control and queue_control.should_pause(job_id):
                    queue_item = _next_queue_item(queue_state, set(timeline_by_video_id))
                    if queue_item:
                        queue_state_service.update_item_status(
                            job_id,
                            queue_item.id,
                            QueueItemStatus.paused,
                            current_step="paused",
                            progress_percent=0,
                        )
                    queue_control.mark_paused(job_id)
                    summary["queue_status"] = "paused"
                    break
                queue_item = _next_queue_item(queue_state, set(timeline_by_video_id))
                if queue_item is None:
                    break
                timeline = timeline_by_video_id[queue_item.video_id]
                _log_queue_chunk_start(queue_state, queue_item, log_callback)
            else:
                if len(outputs) >= len(timelines):
                    break
                timeline = timelines[len(outputs)]

            index = timeline.output_index
            completed_outputs = sum(1 for item in outputs if item["status"] in {"success", "warning"})
            failed_outputs = sum(1 for item in outputs if item["status"] == "failed")
            processed_outputs = completed_outputs + failed_outputs
            base_progress = 30 + int((processed_outputs / max(1, len(timelines))) * 65)
            _progress(
                progress_callback,
                current_step=f"rendering_video_{index}",
                progress=base_progress,
                total_outputs=len(timelines),
                completed_outputs=completed_outputs,
                failed_outputs=failed_outputs,
            )
            _log(log_callback, "info", f"Đang render video {index:03d}")

            if queue_state_service and job_id and queue_item:
                if resource_guard and queue_state:
                    has_resource_warning, resource_warnings = resource_guard.should_warn_before_next_item(queue_state.settings)
                    if has_resource_warning:
                        summary.setdefault("queue_warnings", []).extend(resource_warnings)
                        for warning in resource_warnings:
                            _log(log_callback, "warning", warning)
                        if _has_low_disk_warning(resource_warnings) and queue_control:
                            queue_state_service.update_item_status(
                                job_id,
                                queue_item.id,
                                QueueItemStatus.paused,
                                current_step="resource_guard",
                                progress_percent=0,
                            )
                            queue_control.mark_paused(job_id, resource_warnings[0])
                            summary["queue_status"] = "paused"
                            break
                queue_state_service.update_item_status(
                    job_id,
                    queue_item.id,
                    QueueItemStatus.running,
                    current_step=f"rendering_video_{index}",
                    progress_percent=10,
                )

            try:
                with ffmpeg_timeout(_queue_ffmpeg_timeout_seconds(queue_state)):
                    output_record = render_one_output(
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
            except Exception as exc:
                output_record = _failed_single_output(index, output_dir, str(exc), preview_only=preview_only)
                _log(log_callback, "error", f"Render thất bại cho video {index:03d}: {exc}")
            outputs.append(output_record)

            if queue_state_service and job_id and queue_item:
                queue_state = queue_state_service.update_item_status(
                    job_id,
                    queue_item.id,
                    _queue_status_from_output(output_record),
                    current_step="completed" if output_record.get("status") != "failed" else "failed",
                    progress_percent=100,
                    error_message=_queue_error_from_output(output_record),
                    output_video_path=output_record.get("path"),
                )
                pause_reason = _repeated_failure_pause_reason(queue_state)
                if pause_reason and queue_control:
                    queue_control.mark_paused(job_id, pause_reason)
                    summary["queue_status"] = "paused"
                    break
                if queue_state.settings.cooldown_seconds_between_renders > 0:
                    time.sleep(queue_state.settings.cooldown_seconds_between_renders)
                _collect_garbage_after_chunk(queue_state, queue_item)

        outputs.sort(key=lambda item: int(item.get("index") or 0))

        if job_id and "queue_status" not in summary and queue_state_service:
            final_queue_state = queue_state_service.load_queue_state(job_id)
            if final_queue_state:
                final_status = QueueRunStatus.completed_with_warnings if final_queue_state.failed_items else QueueRunStatus.completed
                final_queue_state = final_queue_state.model_copy(update={"status": final_status})
                queue_state_service.save_queue_state(final_queue_state)
                summary["queue_status"] = final_queue_state.status.value
            else:
                summary["queue_status"] = "completed"

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

    final_queue_status = summary.get("queue_status")
    if final_queue_status in {"paused", "cancelled"}:
        final_step = final_queue_status
        processed = int(summary.get("successful_outputs", 0) or 0) + int(summary.get("failed_outputs", 0) or 0)
        total = max(1, int(summary.get("requested_outputs", working_config.render.output_count) or 1))
        final_progress = min(99, int((processed / total) * 100))
    else:
        final_step = "completed"
        final_progress = 100
    _progress(
        progress_callback,
        current_step=final_step,
        progress=final_progress,
        total_outputs=working_config.render.output_count,
        completed_outputs=summary["successful_outputs"],
        failed_outputs=summary["failed_outputs"],
        status=final_queue_status if final_queue_status in {"paused", "cancelled"} else None,
    )
    return summary


def _timeline_queue_paths(timelines: list[Any]) -> list[str]:
    paths: list[str] = []
    for timeline in timelines:
        first_clip = timeline.clips[0] if getattr(timeline, "clips", None) else None
        paths.append(str(getattr(first_clip, "source_path", "") or f"video_{timeline.output_index:03d}"))
    return paths


def _queue_settings_for_product_render(config: ProjectConfig, preview_only: bool) -> QueueSettings:
    if preview_only or config.render.output_count <= 1:
        return QueueSettings()
    return QueueSettings(max_concurrent_videos=2, allow_parallel_render=True)


def _queue_worker_pool_enabled(queue_state: QueueState) -> bool:
    plan = queue_state.concurrency_plan
    return bool(
        plan
        and plan.worker_pool_enabled
        and queue_state.settings.allow_parallel_render
        and queue_state.settings.max_concurrent_videos > 1
        and queue_state.total_items > 1
    )


def _render_product_queue_parallel(
    *,
    timelines: list[Any],
    timeline_by_video_id: dict[str, Any],
    config: ProjectConfig,
    output_dir: Path,
    custom_script: ProductVideoScript | None,
    script_variants: list[ProductVideoScript] | None,
    preview_only: bool,
    job_id: str,
    queue_state: QueueState,
    queue_state_service: QueueStateService,
    queue_control: QueueControlService,
    resource_guard: ResourceGuardService | None,
    source_filter_summary: dict[str, Any],
    progress_callback: ProgressCallback | None,
    log_callback: LogCallback | None,
) -> list[dict[str, Any]]:
    max_workers = max(1, min(2, int(queue_state.settings.max_concurrent_videos)))
    stage_gate = StageGate(queue_state.concurrency_plan)
    known_video_ids = set(timeline_by_video_id)
    outputs: list[dict[str, Any]] = []
    state_lock = threading.RLock()
    stop_reason: str | None = None
    pause_reason = "Job đã tạm dừng sau các video đang chạy."
    _log(log_callback, "info", f"Bật worker pool product render: {max_workers} video song song.")

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="product-render") as executor:
        futures: dict[Future[dict[str, Any]], tuple[Any, int]] = {}
        while True:
            if stop_reason is None:
                if queue_control.should_cancel(job_id):
                    stop_reason = "cancelled"
                elif queue_control.should_pause(job_id):
                    stop_reason = "paused"

            while stop_reason is None and len(futures) < max_workers:
                with state_lock:
                    current_state = queue_state_service.load_queue_state(job_id) or queue_state
                queue_item = _next_queue_item(current_state, known_video_ids)
                if queue_item is None:
                    break

                if resource_guard:
                    has_resource_warning, resource_warnings = resource_guard.should_warn_before_next_item(current_state.settings)
                    if has_resource_warning:
                        for warning in resource_warnings:
                            _log(log_callback, "warning", warning)
                        if _has_low_disk_warning(resource_warnings):
                            pause_reason = resource_warnings[0]
                            with state_lock:
                                queue_state_service.update_item_status(
                                    job_id,
                                    queue_item.id,
                                    QueueItemStatus.paused,
                                    current_step="resource_guard",
                                    progress_percent=0,
                                )
                            stop_reason = "paused"
                            break

                timeline = timeline_by_video_id[queue_item.video_id]
                index = timeline.output_index
                _log_queue_chunk_start(current_state, queue_item, log_callback)
                _emit_queue_progress(
                    outputs,
                    futures,
                    len(timelines),
                    progress_callback,
                    f"rendering_video_{index}",
                )
                _log(log_callback, "info", f"Đang render video {index:03d} bằng worker pool")
                with state_lock:
                    queue_state_service.update_item_status(
                        job_id,
                        queue_item.id,
                        QueueItemStatus.running,
                        current_step=f"rendering_video_{index}",
                        progress_percent=10,
                    )
                future = executor.submit(
                    _render_one_output_isolated,
                    index=index,
                    timeline=timeline,
                    config=config,
                    output_dir=output_dir,
                    custom_script=custom_script,
                    script_variants=script_variants,
                    preview_only=preview_only,
                    log_callback=log_callback,
                    source_filter_summary=source_filter_summary,
                    stage_gate=stage_gate,
                    ffmpeg_timeout_seconds=queue_state.settings.ffmpeg_timeout_seconds,
                )
                futures[future] = (queue_item, index)

            if not futures:
                break

            done, _ = wait(futures.keys(), timeout=0.5, return_when=FIRST_COMPLETED)
            if not done:
                continue

            for future in done:
                queue_item, index = futures.pop(future)
                try:
                    output_record = future.result()
                except Exception as exc:
                    output_record = _failed_single_output(index, output_dir, str(exc), preview_only=preview_only)
                    _log(log_callback, "error", f"Render thất bại cho video {index:03d}: {exc}")
                outputs.append(output_record)
                with state_lock:
                    latest_state = queue_state_service.update_item_status(
                        job_id,
                        queue_item.id,
                        _queue_status_from_output(output_record),
                        current_step="completed" if output_record.get("status") != "failed" else "failed",
                        progress_percent=100,
                        error_message=_queue_error_from_output(output_record),
                        output_video_path=output_record.get("path"),
                    )
                    repeated_failure_reason = _repeated_failure_pause_reason(latest_state)
                    if repeated_failure_reason and stop_reason is None:
                        pause_reason = repeated_failure_reason
                        stop_reason = "paused"
                _emit_queue_progress(
                    outputs,
                    futures,
                    len(timelines),
                    progress_callback,
                    f"completed_video_{index}",
                )
                cooldown = int(latest_state.settings.cooldown_seconds_between_renders or 0)
                if cooldown > 0:
                    time.sleep(cooldown)
                _collect_garbage_after_chunk(latest_state, queue_item)

    if stop_reason == "cancelled":
        queue_control.mark_cancelled(job_id)
    elif stop_reason == "paused":
        queue_control.mark_paused(job_id, pause_reason)
    return outputs


def _render_one_output_isolated(
    *,
    index: int,
    timeline: Any,
    config: ProjectConfig,
    output_dir: Path,
    custom_script: ProductVideoScript | None,
    script_variants: list[ProductVideoScript] | None,
    preview_only: bool,
    log_callback: LogCallback | None,
    source_filter_summary: dict[str, Any],
    stage_gate: StageGate,
    ffmpeg_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    worker_cache = CacheService.for_project(config, log_callback=log_callback)
    with ffmpeg_timeout(ffmpeg_timeout_seconds):
        return render_one_output(
            index=index,
            timeline=timeline,
            config=config,
            output_dir=output_dir,
            renderer=Renderer(),
            voice_generator=VoiceGenerator(
                cache_service=worker_cache,
                cache_enabled=config.cache.cache_tts,
            ),
            subtitle_generator=SubtitleGenerator(),
            music_selector=MusicSelector(),
            custom_script=custom_script,
            script_override=_script_for_output(index, custom_script, script_variants),
            preview_only=preview_only,
            log_callback=log_callback,
            cache_service=worker_cache,
            source_media_filter_summary=summarize_timeline_source_filter(
                timeline,
                source_filter_summary,
            ),
            stage_gate=stage_gate,
        )


def _emit_queue_progress(
    outputs: list[dict[str, Any]],
    futures: dict[Future[dict[str, Any]], tuple[Any, int]],
    total_outputs: int,
    progress_callback: ProgressCallback | None,
    current_step: str,
) -> None:
    completed_outputs = sum(1 for item in outputs if item.get("status") in {"success", "warning"})
    failed_outputs = sum(1 for item in outputs if item.get("status") == "failed")
    processed_outputs = completed_outputs + failed_outputs
    base_progress = 30 + int((processed_outputs / max(1, total_outputs)) * 65)
    if futures and processed_outputs < total_outputs:
        base_progress = min(94, base_progress + 1)
    _progress(
        progress_callback,
        current_step=current_step,
        progress=base_progress,
        total_outputs=total_outputs,
        completed_outputs=completed_outputs,
        failed_outputs=failed_outputs,
    )


def _next_queue_item(queue_state: QueueState | None, known_video_ids: set[str]):
    if queue_state is None:
        return None
    candidates = [
        item
        for item in queue_state.items
        if item.video_id in known_video_ids and item.status == QueueItemStatus.queued
    ]
    if not candidates:
        return None
    return sorted(candidates, key=_queue_sort_key)[0]


def _queue_sort_key(item) -> tuple[int, int]:
    priority = {
        QueueItemPriority.high: 0,
        QueueItemPriority.normal: 1,
        QueueItemPriority.low: 2,
    }.get(item.priority, 1)
    return (priority, item.order_index)


def _queue_status_from_output(output_record: dict[str, Any]) -> QueueItemStatus:
    status = str(output_record.get("status") or "").lower()
    if status in {"success", "warning"}:
        return QueueItemStatus.completed
    if status == "needs_review":
        return QueueItemStatus.needs_review
    if status == "skipped":
        return QueueItemStatus.skipped
    return QueueItemStatus.failed


def _queue_error_from_output(output_record: dict[str, Any]) -> str | None:
    if output_record.get("status") != "failed":
        return None
    if output_record.get("error"):
        return str(output_record["error"])
    errors = output_record.get("errors")
    if isinstance(errors, list) and errors:
        return str(errors[0])
    return "Render output thất bại."


def _queue_ffmpeg_timeout_seconds(queue_state: QueueState | None) -> int | None:
    if queue_state is None:
        return None
    value = int(queue_state.settings.ffmpeg_timeout_seconds or 0)
    return value or None


def _repeated_failure_pause_reason(queue_state: QueueState | None) -> str | None:
    if queue_state is None or not queue_state.settings.pause_on_repeated_failures:
        return None
    limit = max(1, int(queue_state.settings.max_consecutive_failures or 1))
    processed = [
        item
        for item in sorted(queue_state.items, key=lambda item: item.order_index)
        if item.status in {
            QueueItemStatus.completed,
            QueueItemStatus.failed,
            QueueItemStatus.needs_review,
            QueueItemStatus.skipped,
            QueueItemStatus.cancelled,
            QueueItemStatus.rendered,
        }
    ]
    streak = 0
    for item in reversed(processed):
        if item.status != QueueItemStatus.failed:
            break
        streak += 1
    if streak >= limit:
        return f"Batch đã tạm dừng vì {streak} video liên tiếp bị lỗi. Hãy kiểm tra cấu hình trước khi tiếp tục."
    return None


def _log_queue_chunk_start(queue_state: QueueState | None, queue_item, log_callback: LogCallback | None) -> None:
    if queue_state is None:
        return
    chunk_size = max(1, int(queue_state.settings.batch_chunk_size or 1))
    if (queue_item.order_index - 1) % chunk_size != 0:
        return
    chunk_index = ((queue_item.order_index - 1) // chunk_size) + 1
    chunk_count = queue_state.concurrency_plan.chunk_count if queue_state.concurrency_plan else 0
    suffix = f"/{chunk_count}" if chunk_count else ""
    _log(log_callback, "info", f"Bắt đầu lô {chunk_index}{suffix}: video {queue_item.order_index}/{queue_state.total_items}.")


def _collect_garbage_after_chunk(queue_state: QueueState | None, queue_item) -> None:
    if queue_state is None:
        return
    chunk_size = max(1, int(queue_state.settings.batch_chunk_size or 1))
    if queue_item.order_index % chunk_size == 0:
        gc.collect()


def _failed_single_output(index: int, output_dir: Path, reason: str, preview_only: bool = False) -> dict[str, Any]:
    prefix = "preview" if preview_only else "video"
    name = f"{prefix}_{index:03d}"
    now = datetime.now().replace(microsecond=0).isoformat()
    log_path = output_dir / f"{name}_log.json"
    message = f"Render thất bại cho video {index:03d}: {reason}"
    payload = {
        "index": index,
        "status": "failed",
        "started_at": now,
        "finished_at": now,
        "duration_seconds": 0,
        "steps": [{"name": "render_output", "status": "failed", "message": message}],
        "warnings": [],
        "errors": [message],
    }
    write_json(log_path, payload)
    return {
        "index": index,
        "path": str(output_dir / f"{name}.mp4"),
        "status": "failed",
        "duration": None,
        "error": message,
        "warnings": [],
        "errors": [message],
        "log_file": str(log_path),
    }


def _has_low_disk_warning(warnings: list[str]) -> bool:
    return any("ổ đĩa thấp" in warning.lower() or "disk" in warning.lower() for warning in warnings)


def _preview_config(config: ProjectConfig) -> ProjectConfig:
    render = config.render.model_copy(
        update={
            "output_count": 1,
            "duration": min(config.render.duration, 8.0),
            "sese_enabled": False,  # Always bypass SESE for preview renders
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


def _product_assets_summary(config: ProjectConfig) -> dict[str, Any]:
    reference_assets = len(config.assets.reference_asset_ids)
    poster_assets = len(config.assets.poster_asset_ids)
    main_asset_id = config.assets.main_product_asset_id
    return {
        "total_assets": (1 if main_asset_id else 0) + reference_assets + poster_assets,
        "main_product_asset_id": main_asset_id,
        "reference_assets": reference_assets,
        "poster_assets": poster_assets,
    }


def _progress(callback: ProgressCallback | None, **payload: Any) -> None:
    if callback:
        callback(payload)


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)
