from __future__ import annotations

import json
import inspect
import shutil
import time
import gc
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import ffmpeg_timeout
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_schema import (
    DouyinOutputResult,
    DouyinReupSettings,
    DouyinVideoItem,
    SubtitleSourceResult,
    TranslationResult,
)
from app.modules.douyin_reup.douyin_summary_builder import build_douyin_reup_summary
from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleTimingGuard
from app.modules.douyin_reup.subtitle_translator import SubtitleTranslator
from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService
from app.modules.job_recovery import JobCheckpointService, RecoverableStep
from app.modules.queue_control import (
    QueueControlService,
    QueueItemPriority,
    QueueItemStatus,
    QueueRunStatus,
    QueueSettings,
    QueueState,
    QueueStateService,
    ResourceGuardService,
)
from app.modules.source_media import SourceMediaSelectionService
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_reup_service import is_silent_reup_settings, speech_result_for_video
from app.modules.subtitle_review import SubtitleReviewService
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json

ProgressCallback = Callable[[dict[str, Any]], None]
LogCallback = Callable[[str, str], None]


class DouyinReupService:
    def __init__(
        self,
        scanner: DouyinFolderScanner | None = None,
        source_detector: SubtitleSourceDetector | None = None,
        translator: SubtitleTranslator | None = None,
        timing_guard: SubtitleTimingGuard | None = None,
        render_pipeline: DouyinRenderPipeline | None = None,
        subtitle_review_service: SubtitleReviewService | None = None,
        silent_pipeline: SilentReupPipeline | None = None,
    ) -> None:
        self.scanner = scanner or DouyinFolderScanner()
        self.source_detector = source_detector or SubtitleSourceDetector()
        self.translator = translator or SubtitleTranslator()
        self.timing_guard = timing_guard or SubtitleTimingGuard()
        self.render_pipeline = render_pipeline or DouyinRenderPipeline()
        self.subtitle_review_service = subtitle_review_service or SubtitleReviewService()
        self.silent_pipeline = silent_pipeline or SilentReupPipeline(render_pipeline=self.render_pipeline)

    def process_folder(
        self,
        config: ProjectConfig,
        project_id: str | None = None,
        job_id: str | None = None,
        retry_cache: dict[str, dict[str, Any]] | None = None,
        retry_steps: set[str] | None = None,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> dict[str, Any]:
        total_started = time.perf_counter()
        settings = config.douyin_reup or DouyinReupSettings(enabled=True)
        if not settings.enabled:
            settings = settings.model_copy(update={"enabled": True})

        created_at = datetime.now().replace(microsecond=0)
        output_root = ensure_dir(
            Path(config.output_folder) / f"{config.project_name}-douyin-reup-{created_at.strftime('%Y-%m-%d-%H%M%S')}"
        )
        _log(log_callback, "info", f"Bắt đầu xử lý Douyin Reup: {output_root}")

        scan_started = time.perf_counter()
        videos = self._select_videos(self.scanner.scan_folder(config.source_folder), settings)
        scan_seconds = time.perf_counter() - scan_started
        total = len(videos)
        if total == 0:
            raise RuntimeError(f"Không tìm thấy video hợp lệ trong thư mục Douyin: {config.source_folder}")

        outputs: list[DouyinOutputResult] = []
        subtitle_sources: Counter[str] = Counter()
        completed = 0
        failed = 0
        queue_state_service: QueueStateService | None = None
        queue_control: QueueControlService | None = None
        resource_guard: ResourceGuardService | None = None
        queue_state: QueueState | None = None
        queue_status: str | None = None
        checkpoint_service = JobCheckpointService() if job_id else None
        if job_id:
            queue_state_service = QueueStateService()
            queue_control = QueueControlService(queue_state_service)
            queue_state = queue_state_service.load_queue_state(job_id)
            current_video_paths = [video.path for video in videos]
            if queue_state is None or _queue_state_needs_rebuild(queue_state, current_video_paths):
                queue_state = queue_state_service.create_queue_state(
                    job_id=job_id,
                    mode="silent_immersive" if is_silent_reup_settings(settings) else "douyin_reup",
                    video_paths=current_video_paths,
                    settings=_queue_settings_from_douyin(settings),
                    output_dir=str(output_root),
                    project_id=project_id,
                )
                queue_state = _apply_source_selection_priorities(queue_state_service, queue_state, settings)
            resource_guard = ResourceGuardService(str(output_root))

        _progress(progress_callback, total, completed, failed, "scanned", 5)
        videos_by_id = {f"video_{index:03d}": video for index, video in enumerate(videos, start=1)}
        while True:
            queue_item = None
            if queue_state_service and job_id:
                queue_state = queue_state_service.load_queue_state(job_id) or queue_state
                if queue_control and queue_control.should_cancel(job_id):
                    queue_control.mark_cancelled(job_id)
                    queue_status = "cancelled"
                    break
                if queue_control and queue_control.should_pause(job_id):
                    queue_item = _next_queue_item(queue_state, set(videos_by_id))
                    if queue_item:
                        queue_state_service.update_item_status(
                            job_id,
                            queue_item.id,
                            QueueItemStatus.paused,
                            current_step="paused",
                            progress_percent=0,
                        )
                    queue_control.mark_paused(job_id)
                    queue_status = "paused"
                    break
                queue_item = _next_queue_item(queue_state, set(videos_by_id))
                if queue_item is None:
                    break
                video = videos_by_id[queue_item.video_id]
                index = _queue_video_index(queue_item.video_id)
                _log_queue_chunk_start(queue_state, queue_item, log_callback)
            else:
                if completed + failed >= total:
                    break
                index = completed + failed + 1
                video = videos[index - 1]

            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}", _progress_percent(index - 1, total))
            last_reported_step: str | None = None

            def step_progress(payload: dict[str, Any]) -> None:
                nonlocal queue_state, last_reported_step
                step = str(payload.get("current_step") or "processing")
                phase_progress = max(0, min(100, int(payload.get("progress", 0))))
                overall_progress = max(
                    5,
                    min(99, int(5 + (((completed + failed) + (phase_progress / 100)) / max(1, total)) * 94)),
                )
                _progress(progress_callback, total, completed, failed, f"douyin_video_{index}_{step}", overall_progress)
                if queue_state_service and job_id and queue_item:
                    queue_state = queue_state_service.update_item_status(
                        job_id,
                        queue_item.id,
                        QueueItemStatus.running,
                        current_step=step,
                        progress_percent=max(10, min(95, 10 + int(phase_progress * 0.85))),
                    )
                if step != last_reported_step:
                    _log(log_callback, "info", f"Video {index}/{total}: {step}")
                    last_reported_step = step
            _log(log_callback, "info", f"Đang xử lý Douyin video {index}/{total}: {video.filename}")
            if queue_state_service and job_id and queue_item:
                if resource_guard and queue_state:
                    has_resource_warning, resource_warnings = resource_guard.should_warn_before_next_item(queue_state.settings)
                    if has_resource_warning:
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
                            queue_status = "paused"
                            break
                queue_state_service.update_item_status(
                    job_id,
                    queue_item.id,
                    QueueItemStatus.running,
                    current_step=f"douyin_video_{index}",
                    progress_percent=10,
                )
            try:
                if checkpoint_service and job_id:
                    checkpoint_service.mark_step_started(
                        job_id,
                        f"video_{index:03d}",
                        video.path,
                        _initial_recoverable_step(settings),
                        {"source_video": video.path},
                    )
                with ffmpeg_timeout(_queue_ffmpeg_timeout_seconds(queue_state)):
                    output = self._process_one_video(
                        index=index,
                        video=video,
                        config=config,
                        settings=settings,
                        output_root=output_root,
                        project_id=project_id,
                        job_id=job_id,
                        cached_output=_cached_retry_output(video, retry_cache),
                        retry_steps=retry_steps or {"asr", "translation", "render"},
                        step_progress_callback=step_progress,
                    )
                outputs.append(output)
                subtitle_sources.update([output.subtitle_source or "none"])
                if output.status in {"success", "needs_review"}:
                    completed += 1
                else:
                    failed += 1
                    _log(log_callback, "warning", f"Video {index} lỗi tại {output.failed_step or 'unknown'}: {'; '.join(output.errors)}")
                if checkpoint_service and job_id:
                    _mark_douyin_output_checkpoint(checkpoint_service, job_id, f"video_{index:03d}", output)
            except Exception as exc:
                failed += 1
                output = self._failed_output(index, video, output_root, _friendly_error(str(exc)), settings=settings)
                outputs.append(output)
                subtitle_sources.update([output.subtitle_source or "none"])
                if checkpoint_service and job_id:
                    checkpoint_service.mark_step_failed(
                        job_id,
                        f"video_{index:03d}",
                        _recoverable_step_from_failed_step(output.failed_step),
                        output.error_message or str(exc),
                    )
                _log(log_callback, "error", f"Video {index} thất bại: {output.error_message or exc}")

            if queue_state_service and job_id and queue_item:
                queue_state = queue_state_service.update_item_status(
                    job_id,
                    queue_item.id,
                    _queue_status_from_douyin_output(output),
                    current_step="completed" if output.status != "failed" else (output.failed_step or "failed"),
                    progress_percent=100,
                    error_message=output.error_message or ("; ".join(output.errors) if output.errors else None),
                    output_video_path=output.path or None,
                )
                pause_reason = _repeated_failure_pause_reason(queue_state)
                if pause_reason and queue_control:
                    queue_control.mark_paused(job_id, pause_reason)
                    queue_status = "paused"
                    break
                if queue_state.settings.cooldown_seconds_between_renders > 0:
                    time.sleep(queue_state.settings.cooldown_seconds_between_renders)
                _collect_garbage_after_chunk(queue_state, queue_item)
            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}_done", _progress_percent(index, total))

        if job_id and queue_state_service:
            final_queue_state = queue_state_service.load_queue_state(job_id)
            if final_queue_state and queue_status is None:
                final_status = QueueRunStatus.completed_with_warnings if final_queue_state.failed_items else QueueRunStatus.completed
                final_queue_state = final_queue_state.model_copy(update={"status": final_status})
                queue_state_service.save_queue_state(final_queue_state)
                queue_status = final_queue_state.status.value

        summary = build_douyin_reup_summary(
            config=config,
            output_root=output_root,
            outputs=outputs,
            subtitle_sources=dict(subtitle_sources),
            scan_seconds=scan_seconds,
            total_runtime_seconds=time.perf_counter() - total_started,
        )
        final_qa_summary_path = output_root / "final_qa_summary.json"
        final_qa_summary = dict(summary.model_dump(mode="json").get("final_output_qa") or {})
        final_qa_summary["summary_path"] = str(final_qa_summary_path)
        write_json(final_qa_summary_path, final_qa_summary)
        summary = summary.model_copy(update={"final_output_qa": final_qa_summary})
        summary_file = output_root / "douyin_reup_summary.json"
        summary = summary.model_copy(update={"summary_file": str(summary_file)})
        if queue_status:
            summary = summary.model_copy(update={"queue_status": queue_status})
        if job_id and queue_state_service:
            state = queue_state_service.load_queue_state(job_id)
            if state:
                summary = summary.model_copy(update={"queue": state.model_dump(mode="json")})
        write_json(summary_file, summary.model_dump(mode="json"))
        final_step = queue_status if queue_status in {"paused", "cancelled"} else "completed"
        final_progress = 100 if queue_status != "paused" else _progress_percent(completed + failed, total)
        _progress(progress_callback, total, completed, failed, final_step, final_progress, status=queue_status)
        _log(log_callback, "info", f"Đã ghi tổng kết Douyin Reup: {summary_file}")
        return summary.model_dump(mode="json")

    def _process_one_video(
        self,
        index: int,
        video: DouyinVideoItem,
        config: ProjectConfig,
        settings: DouyinReupSettings,
        output_root: Path,
        project_id: str | None = None,
        job_id: str | None = None,
        cached_output: dict[str, Any] | None = None,
        retry_steps: set[str] | None = None,
        step_progress_callback: ProgressCallback | None = None,
    ) -> DouyinOutputResult:
        if is_silent_reup_settings(settings):
            return self._process_one_silent_video(
                index=index,
                video=video,
                config=config,
                settings=settings,
                output_root=output_root,
                project_id=project_id,
                job_id=job_id,
                step_progress_callback=step_progress_callback,
            )

        video_dir = ensure_dir(output_root / f"video_{index:03d}")
        log_path = video_dir / f"video_{index:03d}_log.json"
        warnings = list(video.warnings)
        errors: list[str] = []
        started_at = datetime.now().replace(microsecond=0)
        steps: dict[str, str] = {"scan": "ok"}
        durations: dict[str, float] = {}
        source_result: SubtitleSourceResult | None = None
        translation: TranslationResult | None = None
        failed_step: str | None = None
        result_status = "success"
        final_qa_report = None
        retry_steps = retry_steps or {"asr", "translation", "render"}
        cached_output = cached_output or {}
        retry_history = _retry_history(cached_output, settings, started_at.isoformat())
        skip_final_log = False

        try:
            cached_source_srt = _existing_cached_path(cached_output.get("source_srt_file"))
            if cached_source_srt:
                source_result = SubtitleSourceResult(
                    video_path=video.path,
                    source_type=cached_output.get("subtitle_source") or "sidecar_srt",
                    source_srt_path=cached_source_srt,
                    language=settings.source_language,
                    warnings=["Dùng lại source SRT đã có từ lần chạy trước."],
                )
                warnings.extend(source_result.warnings)
                steps["subtitle_source"] = "reused"
            else:
                failed_step = "subtitle_source"
                source_started = time.perf_counter()
                _step_progress(step_progress_callback, "subtitle_source", 5)
                detector_kwargs: dict[str, Any] = {}
                if "progress_callback" in inspect.signature(self.source_detector.detect_source).parameters:
                    detector_kwargs["progress_callback"] = step_progress_callback
                source_result = self.source_detector.detect_source(video, settings, str(video_dir), **detector_kwargs)
                if source_result.source_type == "asr":
                    durations["asr_seconds"] = time.perf_counter() - source_started
                    steps["asr"] = "ok"
                if source_result.source_type == "ocr_hardsub":
                    durations["ocr_seconds"] = time.perf_counter() - source_started
                    steps["ocr"] = "ok"
                warnings.extend(source_result.warnings)
                steps["subtitle_source"] = "ok"
            if source_result.source_type == "none" or not source_result.source_srt_path:
                routed = self._route_voice_video_to_silent_if_needed(
                    index=index,
                    video=video,
                    config=config,
                    settings=settings,
                    output_root=output_root,
                    source_result=source_result,
                    project_id=project_id,
                    job_id=job_id,
                    step_progress_callback=step_progress_callback,
                )
                if routed is not None:
                    skip_final_log = True
                    return routed
                errors.extend(source_result.errors)
                if any("ASR" in error.upper() for error in errors):
                    failed_step = "asr"
                raise RuntimeError(_friendly_error("; ".join(errors) or f"Không tìm thấy subtitle nguồn cho video {video.filename}."))

            translated_path = video_dir / f"video_{index:03d}_{settings.target_language}.srt"
            cached_translated_srt = _existing_cached_path(cached_output.get("translated_srt_file"))
            should_retranslate = cached_output.get("failed_step") in {"translation", "translate_subtitle"} and "translation" in retry_steps
            if cached_translated_srt and not should_retranslate:
                translation = TranslationResult(
                    source_srt_path=source_result.source_srt_path,
                    translated_srt_path=cached_translated_srt,
                    provider="retry_cache",
                    source_language=settings.source_language,
                    target_language=settings.target_language,
                    warnings=["Dùng lại translated SRT đã có từ lần chạy trước."],
                )
                warnings.extend(translation.warnings)
                steps["translation"] = "reused"
            else:
                failed_step = "translation"
                _step_progress(step_progress_callback, "translation", 55)
                translation_started = time.perf_counter()
                translation = self.translator.translate_srt(
                    source_result.source_srt_path,
                    str(translated_path),
                    source_language=settings.source_language,
                    target_language=settings.target_language,
                    provider=settings.translation_provider,
                    model_name=config.ai.text_model,
                    api_keys=config.ai.gemini_api_keys,
                )
                durations["translation_seconds"] = time.perf_counter() - translation_started
                warnings.extend(translation.warnings)
                steps["translation"] = "ok"

            fixed_srt_path = video_dir / f"video_{index:03d}_{settings.target_language}_fixed.srt"
            subtitle_offset = settings.asr_subtitle_offset_seconds if source_result.source_type == "asr" else 0.0
            failed_step = "timing_guard"
            _step_progress(step_progress_callback, "timing_guard", 65)
            fixed_srt = self.timing_guard.guard_timing(
                translation.translated_srt_path,
                target_duration=video.duration,
                output_path=str(fixed_srt_path),
                time_offset_seconds=subtitle_offset,
            )
            translation = translation.model_copy(update={"translated_srt_path": fixed_srt})
            steps["timing_guard"] = "ok"

            if settings.review_subtitles_before_render and not settings.auto_render_after_translation:
                failed_step = "review_document"
                cached_document_id = cached_output.get("subtitle_review_document_id")
                document = None
                if cached_document_id:
                    try:
                        document = self.subtitle_review_service.get_document(str(cached_document_id))
                        steps["review_document"] = "reused"
                    except LookupError:
                        document = None
                if document is None:
                    document = self.subtitle_review_service.create_document_from_srt(
                        video_id=f"douyin_{index:03d}",
                        video_path=video.path,
                        translated_srt_path=fixed_srt,
                        source_srt_path=source_result.source_srt_path,
                        project_id=project_id,
                        job_id=job_id,
                        source_language=settings.source_language,
                        target_language=settings.target_language,
                        source_type=source_result.source_type,
                        auto_mark_low_quality_lines=settings.auto_mark_low_quality_lines,
                        enable_subtitle_rewrite_suggestions=settings.enable_subtitle_rewrite_suggestions,
                        auto_generate_rewrite_for_flagged_lines=settings.auto_generate_rewrite_for_flagged_lines,
                        auto_apply_safe_rewrites=settings.auto_apply_safe_rewrites,
                        default_rewrite_style=settings.default_rewrite_style,
                    )
                    steps["review_document"] = "ok"
                warnings.extend([f"Subtitle review required: {document.id}"])
                steps["render"] = "skipped_review_required"
                result_status = "needs_review"
                return DouyinOutputResult(
                    index=index,
                    path="",
                    status="needs_review",
                    source_video=video.path,
                    preset_id=settings.preset_id,
                    preset_name=settings.preset_name,
                    subtitle_source=source_result.source_type,
                    source_srt_file=source_result.source_srt_path,
                    translated_srt_file=fixed_srt,
                    subtitle_review_document_id=document.id,
                    ocr_debug_json_path=source_result.ocr_debug_json_path,
                    ocr_frame_count=source_result.ocr_frame_count,
                    ocr_detected_line_count=source_result.ocr_detected_line_count,
                    ocr_average_confidence=source_result.ocr_average_confidence,
                    ocr_provider=settings.ocr_provider if source_result.source_type == "ocr_hardsub" else None,
                    ocr_region_mode=settings.ocr_region_mode if source_result.source_type == "ocr_hardsub" else None,
                    log_file=str(log_path),
                    duration=video.duration,
                    durations=_round_durations(durations),
                    retry_history=retry_history,
                    warnings=_dedupe(warnings),
                    errors=[],
                )

            failed_step = "render"
            _step_progress(step_progress_callback, "render", 72)
            render_started = time.perf_counter()
            render_kwargs: dict[str, Any] = {
                "video": video,
                "translation_result": translation,
                "settings": settings,
                "output_dir": str(video_dir),
                "output_name": f"douyin_{index:03d}.mp4",
            }
            if "tts_settings" in inspect.signature(self.render_pipeline.render_video_with_translated_subtitle).parameters:
                render_kwargs["tts_settings"] = config.tts
            render_payload = self.render_pipeline.render_video_with_translated_subtitle(**render_kwargs)
            durations["render_seconds"] = time.perf_counter() - render_started
            warnings.extend(render_payload.get("warnings") or [])
            errors.extend(render_payload.get("errors") or [])
            steps["render"] = "ok"
            _step_progress(step_progress_callback, "final_output_qa", 94)
            final_qa_report = FinalOutputQAService().run_qa_for_output(
                str(render_payload["path"]),
                PlatformTarget.tiktok,
                job_id=job_id,
                project_id=project_id,
                video_id=f"douyin_{index:03d}",
                ass_path=render_payload.get("subtitle_ass_file"),
                overlay_path=render_payload.get("overlay_file"),
                subtitle_expected=settings.burn_subtitle,
                audio_expected=settings.keep_original_audio or settings.add_bgm or settings.generate_voiceover_for_silent_video,
                overlay_expected=settings.add_overlay,
                report_path=str(video_dir / f"video_{index:03d}_final_qa.json"),
            )
            steps["final_output_qa"] = final_qa_report.status

            return DouyinOutputResult(
                index=index,
                path=str(render_payload["path"]),
                status="success",
                source_video=video.path,
                preset_id=settings.preset_id,
                preset_name=settings.preset_name,
                subtitle_source=source_result.source_type,
                source_srt_file=source_result.source_srt_path,
                translated_srt_file=fixed_srt,
                subtitle_ass_file=render_payload.get("subtitle_ass_file"),
                overlay_file=render_payload.get("overlay_file"),
                bgm_file=render_payload.get("bgm_file"),
                voiceover_file=render_payload.get("voiceover_file"),
                log_file=str(log_path),
                ocr_debug_json_path=source_result.ocr_debug_json_path,
                ocr_frame_count=source_result.ocr_frame_count,
                ocr_detected_line_count=source_result.ocr_detected_line_count,
                ocr_average_confidence=source_result.ocr_average_confidence,
                ocr_provider=settings.ocr_provider if source_result.source_type == "ocr_hardsub" else None,
                ocr_region_mode=settings.ocr_region_mode if source_result.source_type == "ocr_hardsub" else None,
                duration=render_payload.get("duration"),
                durations=_round_durations(durations),
                retry_history=retry_history,
                final_output_qa=_final_qa_summary(final_qa_report),
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
        except Exception as exc:
            result_status = "failed"
            error_message = _friendly_error(str(exc))
            errors.append(error_message)
            if failed_step:
                steps[failed_step] = "failed"
            return DouyinOutputResult(
                index=index,
                path="",
                status="failed",
                source_video=video.path,
                preset_id=settings.preset_id,
                preset_name=settings.preset_name,
                subtitle_source=source_result.source_type if source_result else None,
                source_srt_file=source_result.source_srt_path if source_result else None,
                translated_srt_file=translation.translated_srt_path if translation else None,
                log_file=str(log_path),
                ocr_debug_json_path=source_result.ocr_debug_json_path if source_result else None,
                ocr_frame_count=source_result.ocr_frame_count if source_result else 0,
                ocr_detected_line_count=source_result.ocr_detected_line_count if source_result else 0,
                ocr_average_confidence=source_result.ocr_average_confidence if source_result else 0.0,
                ocr_provider=settings.ocr_provider if source_result and source_result.source_type == "ocr_hardsub" else None,
                ocr_region_mode=settings.ocr_region_mode if source_result and source_result.source_type == "ocr_hardsub" else None,
                failed_step=failed_step or "process_video",
                error_message=error_message,
                can_retry=True,
                duration=video.duration,
                durations=_round_durations(durations),
                retry_history=retry_history,
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
        finally:
            if not skip_final_log:
                finished_at = datetime.now().replace(microsecond=0)
                payload: dict[str, Any] = {
                    "index": index,
                    "input_video": video.path,
                    "status": result_status,
                    "preset_id": settings.preset_id,
                    "preset_name": settings.preset_name,
                    "started_at": started_at.isoformat(),
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": max(0.0, (finished_at - started_at).total_seconds()),
                    "source_video": video.path,
                    "steps": steps,
                    "durations": _round_durations(durations),
                    "retry_history": retry_history,
                    "warnings": _dedupe(warnings),
                    "errors": _dedupe(errors),
                }
                if errors:
                    payload.update(
                        {
                            "failed_step": failed_step or "process_video",
                            "error_message": _dedupe(errors)[-1],
                            "can_retry": True,
                        }
                    )
                if source_result and source_result.source_type == "ocr_hardsub":
                    payload["ocr"] = {
                        "enabled": True,
                        "provider": settings.ocr_provider,
                        "region_mode": settings.ocr_region_mode,
                        "sample_fps": settings.ocr_sample_fps,
                        "frame_count": source_result.ocr_frame_count,
                        "detected_line_count": source_result.ocr_detected_line_count,
                        "average_confidence": source_result.ocr_average_confidence,
                        "source_srt_path": source_result.source_srt_path,
                        "debug_json_path": source_result.ocr_debug_json_path,
                        "warnings": [warning for warning in warnings if "OCR" in warning or "ocr" in warning],
                    }
                if final_qa_report is not None:
                    payload["final_output_qa"] = _final_qa_summary(final_qa_report)
                write_json(log_path, payload)

    def _process_one_silent_video(
        self,
        index: int,
        video: DouyinVideoItem,
        config: ProjectConfig,
        settings: DouyinReupSettings,
        output_root: Path,
        project_id: str | None = None,
        job_id: str | None = None,
        step_progress_callback: ProgressCallback | None = None,
    ) -> DouyinOutputResult:
        video_dir = ensure_dir(output_root / f"video_{index:03d}")
        log_path = video_dir / f"video_{index:03d}_log.json"
        warnings = list(video.warnings)
        errors: list[str] = []
        started_at = datetime.now().replace(microsecond=0)
        steps: dict[str, str] = {"scan": "ok", "mode": "silent_immersive"}
        durations: dict[str, float] = {}
        failed_step: str | None = None
        result_status = "success"
        final_qa_report = None
        plan = None
        render_result = None
        caption_srt_path: str | None = None
        caption_source: str | None = None
        document_id: str | None = None

        routed = self._route_silent_video_to_voice_if_needed(
            index=index,
            video=video,
            config=config,
            settings=settings,
            output_root=output_root,
            project_id=project_id,
            job_id=job_id,
            step_progress_callback=step_progress_callback,
        )
        if routed is not None:
            return routed

        try:
            failed_step = "silent_plan"
            _step_progress(step_progress_callback, "silent_plan", 5)
            plan_started = time.perf_counter()
            plan_kwargs: dict[str, Any] = {
                "video_path": video.path,
                "settings": settings,
                "output_dir": str(video_dir),
                "product_context": _product_context(config),
                "gemini_api_keys": config.ai.gemini_api_keys,
            }
            if "progress_callback" in inspect.signature(self.silent_pipeline.build_plan).parameters:
                plan_kwargs["progress_callback"] = _mapped_progress_callback(
                    step_progress_callback, 5, 70, "silent_plan"
                )
            plan = self.silent_pipeline.build_plan(**plan_kwargs)
            durations["silent_plan_seconds"] = time.perf_counter() - plan_started
            warnings.extend(plan.warnings)
            caption_source = _silent_caption_source(plan)
            steps["silent_plan"] = "ok"

            failed_step = "silent_caption_srt"
            _step_progress(step_progress_callback, "silent_caption_srt", 72)
            caption_srt_path = self.silent_pipeline.write_caption_srt(
                plan,
                str(video_dir),
                f"video_{index:03d}_silent_vi.srt",
            )
            steps["silent_caption_srt"] = "ok"

            if settings.silent_review_before_render and not settings.auto_render_after_translation:
                failed_step = "review_document"
                document = self.subtitle_review_service.create_document_from_srt(
                    video_id=f"douyin_silent_{index:03d}",
                    video_path=video.path,
                    translated_srt_path=caption_srt_path,
                    source_srt_path=self.silent_pipeline.last_ocr_source_srt_path,
                    project_id=project_id,
                    job_id=job_id,
                    source_language=settings.source_language,
                    target_language=settings.target_language,
                    source_type=caption_source or "visual_generated",
                    context={
                        "reup_mode": "silent_immersive",
                        "silent_strategy": plan.strategy,
                        "silent_plan_file": self.silent_pipeline.last_plan_path,
                        "speech_score": plan.speech_score,
                        "has_speech": plan.has_speech,
                        "recommended_audio_mode": plan.recommended_audio_mode,
                        "generate_voiceover": settings.generate_voiceover_for_silent_video,
                        "voiceover_script_file": self.silent_pipeline.last_voiceover_script_path,
                        "voiceover_subtitle_file": self.silent_pipeline.last_voiceover_subtitle_path,
                        "product_context": _product_context(config),
                        "visual_tagging": plan.visual_tagging.model_dump(mode="json"),
                        "visual_tag_report": plan.visual_tag_report.model_dump(mode="json") if plan.visual_tag_report else None,
                        "settings_snapshot": settings.model_dump(mode="json"),
                    },
                    auto_mark_low_quality_lines=settings.auto_mark_low_quality_lines,
                    enable_subtitle_rewrite_suggestions=settings.enable_subtitle_rewrite_suggestions,
                    auto_generate_rewrite_for_flagged_lines=settings.auto_generate_rewrite_for_flagged_lines,
                    auto_apply_safe_rewrites=settings.auto_apply_safe_rewrites,
                    default_rewrite_style=settings.default_rewrite_style,
                )
                document_id = document.id
                warnings.append(f"Subtitle review required: {document.id}")
                steps["review_document"] = "ok"
                steps["render"] = "skipped_review_required"
                result_status = "needs_review"
                return DouyinOutputResult(
                    index=index,
                    path="",
                    status="needs_review",
                    source_video=video.path,
                    preset_id=settings.preset_id,
                    preset_name=settings.preset_name,
                    subtitle_source=caption_source or "visual_generated",
                    source_srt_file=self.silent_pipeline.last_ocr_source_srt_path,
                    translated_srt_file=caption_srt_path,
                    subtitle_review_document_id=document.id,
                    reup_mode="silent_immersive",
                    silent_strategy=plan.strategy,
                    speech_score=plan.speech_score,
                    caption_source=caption_source,
                    silent_plan_file=self.silent_pipeline.last_plan_path,
                    silent_caption_generation=plan.caption_generation.model_dump(mode="json"),
                    silent_visual_tagging=plan.visual_tagging.model_dump(mode="json"),
                    voiceover_script_file=self.silent_pipeline.last_voiceover_script_path,
                    voiceover_subtitle_file=self.silent_pipeline.last_voiceover_subtitle_path,
                    ocr_debug_json_path=self.silent_pipeline.last_ocr_debug_json_path,
                    ocr_frame_count=self.silent_pipeline.last_ocr_frame_count,
                    ocr_detected_line_count=self.silent_pipeline.last_ocr_detected_line_count,
                    ocr_average_confidence=self.silent_pipeline.last_ocr_average_confidence,
                    ocr_provider=settings.ocr_provider if self.silent_pipeline.last_ocr_source_srt_path else None,
                    ocr_region_mode=settings.ocr_region_mode if self.silent_pipeline.last_ocr_source_srt_path else None,
                    log_file=str(log_path),
                    duration=video.duration,
                    durations=_round_durations(durations),
                    retry_history=[],
                    warnings=_dedupe(warnings),
                    errors=[],
                )

            failed_step = "silent_render"
            _step_progress(step_progress_callback, "silent_render", 78)
            render_started = time.perf_counter()
            render_kwargs: dict[str, Any] = {}
            if "progress_callback" in inspect.signature(self.silent_pipeline.render_from_plan).parameters:
                render_kwargs["progress_callback"] = _mapped_progress_callback(
                    step_progress_callback, 78, 94, "silent_render"
                )
            if "tts_settings" in inspect.signature(self.silent_pipeline.render_from_plan).parameters:
                render_kwargs["tts_settings"] = config.tts
            render_result = self.silent_pipeline.render_from_plan(plan, settings, str(video_dir), **render_kwargs)
            durations["render_seconds"] = time.perf_counter() - render_started
            warnings.extend(render_result.warnings)
            errors.extend(render_result.errors)
            if render_result.status != "success" or not render_result.output_video_path:
                raise RuntimeError("; ".join(render_result.errors) or "Silent render không tạo được video final.")
            steps["render"] = "ok"

            _step_progress(step_progress_callback, "final_output_qa", 95)
            final_qa_report = FinalOutputQAService().run_qa_for_output(
                render_result.output_video_path,
                PlatformTarget.tiktok,
                job_id=job_id,
                project_id=project_id,
                video_id=f"douyin_silent_{index:03d}",
                ass_path=render_result.caption_ass_path,
                overlay_path=render_result.overlay_path,
                subtitle_expected=settings.burn_subtitle,
                audio_expected=(
                    settings.keep_immersive_original_audio
                    or settings.add_bgm_for_silent_video
                    or settings.generate_voiceover_for_silent_video
                ),
                overlay_expected=settings.add_overlay,
                report_path=str(video_dir / f"video_{index:03d}_final_qa.json"),
            )
            steps["final_output_qa"] = final_qa_report.status

            return DouyinOutputResult(
                index=index,
                path=render_result.output_video_path,
                status="success",
                source_video=video.path,
                preset_id=settings.preset_id,
                preset_name=settings.preset_name,
                subtitle_source=caption_source or "visual_generated",
                source_srt_file=self.silent_pipeline.last_ocr_source_srt_path,
                translated_srt_file=render_result.caption_srt_path,
                subtitle_ass_file=render_result.caption_ass_path,
                bgm_file=render_result.bgm_path,
                log_file=str(log_path),
                reup_mode="silent_immersive",
                silent_strategy=plan.strategy,
                speech_score=plan.speech_score,
                caption_source=caption_source,
                silent_plan_file=render_result.plan_path,
                silent_caption_generation=plan.caption_generation.model_dump(mode="json"),
                silent_visual_tagging=plan.visual_tagging.model_dump(mode="json"),
                voiceover_file=render_result.voiceover_path,
                voiceover_script_file=self.silent_pipeline.last_voiceover_script_path,
                voiceover_subtitle_file=render_result.voiceover_subtitle_path,
                ocr_debug_json_path=self.silent_pipeline.last_ocr_debug_json_path,
                ocr_frame_count=self.silent_pipeline.last_ocr_frame_count,
                ocr_detected_line_count=self.silent_pipeline.last_ocr_detected_line_count,
                ocr_average_confidence=self.silent_pipeline.last_ocr_average_confidence,
                ocr_provider=settings.ocr_provider if self.silent_pipeline.last_ocr_source_srt_path else None,
                ocr_region_mode=settings.ocr_region_mode if self.silent_pipeline.last_ocr_source_srt_path else None,
                duration=video.duration,
                durations=_round_durations(durations),
                retry_history=[],
                final_output_qa=_final_qa_summary(final_qa_report),
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
        except Exception as exc:
            result_status = "failed"
            error_message = _friendly_error(str(exc))
            errors.append(error_message)
            if failed_step:
                steps[failed_step] = "failed"
            return DouyinOutputResult(
                index=index,
                path="",
                status="failed",
                source_video=video.path,
                preset_id=settings.preset_id,
                preset_name=settings.preset_name,
                subtitle_source=caption_source,
                source_srt_file=self.silent_pipeline.last_ocr_source_srt_path,
                translated_srt_file=caption_srt_path,
                log_file=str(log_path),
                reup_mode="silent_immersive",
                silent_strategy=plan.strategy if plan else settings.silent_mode_strategy,
                speech_score=plan.speech_score if plan else None,
                caption_source=caption_source,
                silent_plan_file=self.silent_pipeline.last_plan_path,
                voiceover_file=render_result.voiceover_path if render_result else None,
                voiceover_script_file=self.silent_pipeline.last_voiceover_script_path,
                voiceover_subtitle_file=(render_result.voiceover_subtitle_path if render_result else self.silent_pipeline.last_voiceover_subtitle_path),
                ocr_debug_json_path=self.silent_pipeline.last_ocr_debug_json_path,
                ocr_frame_count=self.silent_pipeline.last_ocr_frame_count,
                ocr_detected_line_count=self.silent_pipeline.last_ocr_detected_line_count,
                ocr_average_confidence=self.silent_pipeline.last_ocr_average_confidence,
                failed_step=failed_step or "silent_process",
                error_message=error_message,
                can_retry=True,
                duration=video.duration,
                durations=_round_durations(durations),
                retry_history=[],
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )
        finally:
            finished_at = datetime.now().replace(microsecond=0)
            payload: dict[str, Any] = {
                "index": index,
                "input_video": video.path,
                "status": result_status,
                "preset_id": settings.preset_id,
                "preset_name": settings.preset_name,
                "reup_mode": "silent_immersive",
                "silent_strategy": plan.strategy if plan else settings.silent_mode_strategy,
                "speech_score": plan.speech_score if plan else None,
                "caption_source": caption_source,
                "subtitle_review_document_id": document_id,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": max(0.0, (finished_at - started_at).total_seconds()),
                "source_video": video.path,
                "steps": steps,
                "durations": _round_durations(durations),
                "warnings": _dedupe(warnings),
                "errors": _dedupe(errors),
                "silent_plan_file": self.silent_pipeline.last_plan_path,
                "caption_srt_path": caption_srt_path or (render_result.caption_srt_path if render_result else None),
                "voiceover_file": render_result.voiceover_path if render_result else None,
                "voiceover_script_file": self.silent_pipeline.last_voiceover_script_path,
                "voiceover_subtitle_file": (
                    render_result.voiceover_subtitle_path if render_result else self.silent_pipeline.last_voiceover_subtitle_path
                ),
                "ocr_debug_json_path": self.silent_pipeline.last_ocr_debug_json_path,
                "visual_tagging": plan.visual_tagging.model_dump(mode="json") if plan else None,
            }
            if errors:
                payload.update(
                    {
                        "failed_step": failed_step or "silent_process",
                        "error_message": _dedupe(errors)[-1],
                        "can_retry": True,
                    }
                )
            if final_qa_report is not None:
                payload["final_output_qa"] = _final_qa_summary(final_qa_report)
            write_json(log_path, payload)

    def _route_silent_video_to_voice_if_needed(
        self,
        *,
        index: int,
        video: DouyinVideoItem,
        config: ProjectConfig,
        settings: DouyinReupSettings,
        output_root: Path,
        project_id: str | None,
        job_id: str | None,
        step_progress_callback: ProgressCallback | None,
    ) -> DouyinOutputResult | None:
        if not (
            settings.auto_route_speech_to_voice_reup
            and settings.detect_speech_presence
            and settings.silent_mode_detection
        ):
            return None

        route_settings = settings.model_copy(
            update={"speech_detection_threshold": settings.auto_route_speech_threshold}
        )
        _step_progress(step_progress_callback, "speech_route_check", 3)
        speech = speech_result_for_video(video.path, route_settings)
        if not speech.has_speech:
            return None

        routed_settings = _voice_reup_settings_from_silent(settings)
        routed_warning = (
            "Tự động chuyển video này sang flow có thoại vì phát hiện tín hiệu lời thoại "
            f"(điểm {speech.speech_score:.2f}, ngưỡng {settings.auto_route_speech_threshold:.2f})."
        )
        warnings = _dedupe([*video.warnings, routed_warning, *speech.warnings])
        routed_video = video.model_copy(update={"warnings": warnings})
        output = self._process_one_video(
            index=index,
            video=routed_video,
            config=config.model_copy(update={"douyin_reup": routed_settings}),
            settings=routed_settings,
            output_root=output_root,
            project_id=project_id,
            job_id=job_id,
            cached_output=None,
            retry_steps={"asr", "translation", "render"},
            step_progress_callback=step_progress_callback,
        )
        return output.model_copy(
            update={
                "reup_mode": "auto_routed_voice_reup",
                "speech_score": speech.speech_score,
                "warnings": _dedupe([*output.warnings, routed_warning, *speech.warnings]),
            }
        )

    def _route_voice_video_to_silent_if_needed(
        self,
        *,
        index: int,
        video: DouyinVideoItem,
        config: ProjectConfig,
        settings: DouyinReupSettings,
        output_root: Path,
        source_result: SubtitleSourceResult,
        project_id: str | None,
        job_id: str | None,
        step_progress_callback: ProgressCallback | None,
    ) -> DouyinOutputResult | None:
        if not (
            settings.auto_route_no_speech_to_silent_reup
            and settings.enable_silent_immersive_mode
            and settings.silent_mode_detection
            and settings.detect_speech_presence
        ):
            return None
        if _has_blocking_subtitle_source_failure(source_result):
            return None

        _step_progress(step_progress_callback, "speech_silent_route_check", 12)
        speech = speech_result_for_video(video.path, settings)
        if speech.has_speech:
            return None

        routed_settings = _silent_reup_settings_from_voice(settings)
        routed_warning = (
            "Tự động chuyển video này sang Silent Mode vì flow có thoại không tìm được phụ đề/ASR hợp lệ "
            f"và không phát hiện lời thoại rõ (điểm {speech.speech_score:.2f}, ngưỡng {settings.speech_detection_threshold:.2f})."
        )
        warnings = _dedupe([*video.warnings, routed_warning, *source_result.warnings, *source_result.errors, *speech.warnings])
        routed_video = video.model_copy(update={"warnings": warnings})
        output = self._process_one_silent_video(
            index=index,
            video=routed_video,
            config=config.model_copy(update={"douyin_reup": routed_settings}),
            settings=routed_settings,
            output_root=output_root,
            project_id=project_id,
            job_id=job_id,
            step_progress_callback=step_progress_callback,
        )
        return output.model_copy(
            update={
                "reup_mode": "auto_routed_silent_immersive",
                "speech_score": speech.speech_score,
                "warnings": _dedupe([*output.warnings, routed_warning, *source_result.warnings, *source_result.errors, *speech.warnings]),
            }
        )

    def _select_videos(self, videos: list[DouyinVideoItem], settings: DouyinReupSettings) -> list[DouyinVideoItem]:
        if settings.process_mode == "selected":
            by_path = {str(Path(video.path).expanduser().resolve()).lower(): video for video in videos}
            selected_videos: list[DouyinVideoItem] = []
            seen: set[str] = set()
            for selected_path in settings.selected_video_paths:
                key = str(Path(selected_path).expanduser().resolve()).lower()
                if key in seen:
                    continue
                video = by_path.get(key)
                if video is not None:
                    selected_videos.append(video)
                    seen.add(key)
            videos = selected_videos
        if settings.process_mode == "first_n" and settings.max_videos:
            videos = videos[: settings.max_videos]
        elif settings.max_videos:
            videos = videos[: settings.max_videos]
        return videos

    def _failed_output(
        self,
        index: int,
        video: DouyinVideoItem,
        output_root: Path,
        reason: str,
        settings: DouyinReupSettings | None = None,
    ) -> DouyinOutputResult:
        video_dir = ensure_dir(output_root / f"video_{index:03d}")
        log_path = video_dir / f"video_{index:03d}_log.json"
        try:
            shutil.copy2(video.path, video_dir / "source.mp4")
        except OSError:
            pass
        error_message = _friendly_error(reason)
        write_json(
            log_path,
            {
                "index": index,
                "input_video": video.path,
                "status": "failed",
                "preset_id": settings.preset_id if settings else None,
                "preset_name": settings.preset_name if settings else None,
                "source_video": video.path,
                "steps": {"process_video": "failed"},
                "durations": {},
                "failed_step": "process_video",
                "error_message": error_message,
                "can_retry": True,
                "warnings": video.warnings,
                "errors": [error_message],
            },
        )
        return DouyinOutputResult(
            index=index,
            path="",
            status="failed",
            source_video=video.path,
            preset_id=settings.preset_id if settings else None,
            preset_name=settings.preset_name if settings else None,
            log_file=str(log_path),
            failed_step="process_video",
            error_message=error_message,
            can_retry=True,
            warnings=video.warnings,
            errors=[error_message],
        )


def _product_context(config: ProjectConfig) -> dict[str, Any]:
    product = config.product
    return {
        "product_name": product.name,
        "name": product.name,
        "brand": product.brand,
        "description": product.description,
        "features": list(product.features),
        "cta": product.cta,
        "category": config.industry.preset_id if config.industry else None,
        "industry": config.industry.preset_id if config.industry else None,
    }


def _voice_reup_settings_from_silent(settings: DouyinReupSettings) -> DouyinReupSettings:
    generate_voiceover = bool(settings.generate_voiceover_for_silent_video)
    return settings.model_copy(
        update={
            "preset_id": "voice_priority",
            "preset_name": "Tự động chuyển sang video có thoại",
            "enable_silent_immersive_mode": False,
            "silent_mode_detection": False,
            "auto_route_no_speech_to_silent_reup": False,
            "subtitle_source_priority": ["sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub"],
            "use_sidecar_srt": True,
            "use_embedded_subtitle": True,
            "use_asr_if_no_subtitle": True,
            "use_ocr_if_asr_failed": True,
            "use_ocr_if_no_subtitle": False,
            "prefer_ocr_over_asr_when_text_visible": False,
            "add_bgm": bool(settings.add_bgm_for_silent_video or settings.add_bgm),
            "bgm_volume": settings.immersive_bgm_volume if settings.add_bgm_for_silent_video else settings.bgm_volume,
            "keep_original_audio": False if generate_voiceover else settings.keep_immersive_original_audio,
            "original_audio_volume": 0.0 if generate_voiceover else settings.immersive_original_audio_volume,
            "generate_voiceover_for_silent_video": generate_voiceover,
            "silent_voiceover_provider": settings.silent_voiceover_provider,
            "silent_voiceover_voice": settings.silent_voiceover_voice,
        }
    )


def _silent_reup_settings_from_voice(settings: DouyinReupSettings) -> DouyinReupSettings:
    generate_voiceover = bool(settings.generate_voiceover_for_silent_video)
    return settings.model_copy(
        update={
            "preset_id": "silent_chill_immersive",
            "preset_name": "Tự động chuyển sang video không thoại",
            "enable_silent_immersive_mode": True,
            "silent_mode_detection": True,
            "silent_mode_strategy": "product_review_voiceover" if generate_voiceover else "chill_immersive",
            "auto_route_speech_to_voice_reup": False,
            "auto_route_no_speech_to_silent_reup": False,
            "silent_review_before_render": settings.review_subtitles_before_render and not settings.auto_render_after_translation,
            "review_subtitles_before_render": settings.review_subtitles_before_render,
            "auto_render_after_translation": settings.auto_render_after_translation,
            "add_bgm_for_silent_video": settings.add_bgm,
            "immersive_bgm_volume": settings.bgm_volume,
            "keep_immersive_original_audio": settings.keep_original_audio,
            "immersive_original_audio_volume": settings.original_audio_volume,
            "generate_voiceover_for_silent_video": generate_voiceover,
            "silent_voiceover_provider": settings.silent_voiceover_provider,
            "silent_voiceover_voice": settings.silent_voiceover_voice,
        }
    )


def _silent_caption_source(plan) -> str:
    if not plan or not plan.captions:
        return "template"
    sources = [caption.source for caption in plan.captions]
    if "ocr_translation" in sources:
        return "ocr_translation"
    if "visual_generated" in sources:
        return "visual_generated"
    return sources[0] if sources else "template"


def _has_blocking_subtitle_source_failure(source_result: SubtitleSourceResult) -> bool:
    for error in source_result.errors:
        normalized = str(error).lower()
        if "asr" in normalized and ("failed" in normalized or "thất bại" in normalized):
            return True
    return False


def _progress(
    callback: ProgressCallback | None,
    total: int,
    completed: int,
    failed: int,
    current_step: str,
    progress: int,
    status: str | None = None,
) -> None:
    if not callback:
        return
    payload = {
        "current_step": current_step,
        "progress": progress,
        "total_outputs": total,
        "completed_outputs": completed,
        "failed_outputs": failed,
    }
    if status:
        payload["status"] = status
    callback(payload)


def _step_progress(callback: ProgressCallback | None, current_step: str, progress: int) -> None:
    if callback:
        callback({"current_step": current_step, "progress": max(0, min(100, int(progress)))})


def _mapped_progress_callback(
    callback: ProgressCallback | None,
    start: int,
    end: int,
    prefix: str,
) -> ProgressCallback | None:
    if callback is None:
        return None

    def mapped(payload: dict[str, Any]) -> None:
        source_progress = max(0, min(100, int(payload.get("progress", 0))))
        step = str(payload.get("current_step") or "processing")
        callback(
            {
                **payload,
                "current_step": f"{prefix}_{step}",
                "progress": start + int((source_progress / 100) * max(0, end - start)),
            }
        )

    return mapped


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)


def _progress_percent(done: int, total: int) -> int:
    if total <= 0:
        return 100
    return max(5, min(99, int((done / total) * 95) + 5))


def _initial_recoverable_step(settings: DouyinReupSettings) -> RecoverableStep:
    return RecoverableStep.caption_generation if is_silent_reup_settings(settings) else RecoverableStep.subtitle_source


def _mark_douyin_output_checkpoint(
    checkpoint_service: JobCheckpointService,
    job_id: str,
    video_id: str,
    output: DouyinOutputResult,
) -> None:
    if output.status in {"success", "needs_review"}:
        step = RecoverableStep.review_document if output.status == "needs_review" else RecoverableStep.render
        output_paths = {
            "video": output.path or "",
            "log": output.log_file or "",
            "source_srt": output.source_srt_file or "",
            "translated_srt": output.translated_srt_file or "",
            "subtitle_review_document_id": output.subtitle_review_document_id or "",
        }
        checkpoint_service.mark_step_completed(job_id, video_id, step, output_paths)
        return

    checkpoint_service.mark_step_failed(
        job_id,
        video_id,
        _recoverable_step_from_failed_step(output.failed_step),
        output.error_message or "; ".join(output.errors) or "Douyin output failed.",
    )


def _recoverable_step_from_failed_step(failed_step: str | None) -> RecoverableStep:
    value = (failed_step or "").strip().lower()
    if "asr" in value:
        return RecoverableStep.asr
    if "ocr" in value:
        return RecoverableStep.ocr
    if "translation" in value or "translate" in value:
        return RecoverableStep.translation
    if "timing" in value or "quality" in value:
        return RecoverableStep.quality_check
    if "review" in value:
        return RecoverableStep.review_document
    if "caption" in value or "silent_plan" in value:
        return RecoverableStep.caption_generation
    if "visual" in value:
        return RecoverableStep.visual_tagging
    if "tts" in value or "voice" in value:
        return RecoverableStep.tts
    if "qa" in value:
        return RecoverableStep.final_qa
    if "render" in value:
        return RecoverableStep.render
    if "subtitle_source" in value or "source" in value:
        return RecoverableStep.subtitle_source
    return RecoverableStep.render


def _queue_state_needs_rebuild(queue_state: QueueState, video_paths: list[str]) -> bool:
    if queue_state.total_items != len(video_paths):
        return True
    current = [str(Path(path).expanduser().resolve()).lower() for path in video_paths]
    existing = [str(Path(item.video_path).expanduser().resolve()).lower() for item in queue_state.items]
    return current != existing


def _apply_source_selection_priorities(
    queue_state_service: QueueStateService,
    queue_state: QueueState,
    settings: DouyinReupSettings,
) -> QueueState:
    if not settings.source_selection_id:
        return queue_state
    priorities_by_path = SourceMediaSelectionService().get_priority_by_path(settings.source_selection_id)
    if not priorities_by_path:
        return queue_state
    changed = False
    items = []
    for item in queue_state.items:
        priority = priorities_by_path.get(str(Path(item.video_path).expanduser().resolve()).lower())
        if priority in {QueueItemPriority.low.value, QueueItemPriority.normal.value, QueueItemPriority.high.value}:
            items.append(item.model_copy(update={"priority": QueueItemPriority(priority)}))
            changed = True
        else:
            items.append(item)
    if not changed:
        return queue_state
    return queue_state_service.save_queue_state(queue_state.model_copy(update={"items": items}))


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


def _queue_video_index(video_id: str) -> int:
    try:
        return int(video_id.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        return 1


def _queue_status_from_douyin_output(output: DouyinOutputResult) -> QueueItemStatus:
    if output.status == "success":
        return QueueItemStatus.completed
    if output.status == "needs_review":
        return QueueItemStatus.needs_review
    if output.status == "skipped":
        return QueueItemStatus.skipped
    return QueueItemStatus.failed


def _queue_ffmpeg_timeout_seconds(queue_state: QueueState | None) -> int | None:
    if queue_state is None:
        return None
    value = int(queue_state.settings.ffmpeg_timeout_seconds or 0)
    return value or None


def _queue_settings_from_douyin(settings: DouyinReupSettings) -> QueueSettings:
    return QueueSettings(
        max_videos_per_batch=settings.max_videos,
        performance_mode=settings.batch_performance_mode,
        batch_chunk_size=settings.batch_chunk_size,
        item_timeout_seconds=settings.batch_item_timeout_seconds,
        ffmpeg_timeout_seconds=settings.batch_ffmpeg_timeout_seconds,
        watchdog_stale_minutes=settings.batch_watchdog_stale_minutes,
        pause_on_repeated_failures=settings.batch_pause_on_repeated_failures,
        max_consecutive_failures=settings.batch_max_consecutive_failures,
        resource_guard_enabled=True,
        continue_on_video_error=True,
    )


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


def _has_low_disk_warning(warnings: list[str]) -> bool:
    return any("ổ đĩa thấp" in warning.lower() or "disk" in warning.lower() for warning in warnings)


def _cached_retry_output(video: DouyinVideoItem, retry_cache: dict[str, dict[str, Any]] | None) -> dict[str, Any] | None:
    if not retry_cache:
        return None
    keys = {
        str(Path(video.path).expanduser().resolve()).lower(),
        video.path,
        video.filename,
    }
    for key in keys:
        if key in retry_cache:
            return retry_cache[key]
    return None


def _final_qa_summary(report) -> dict | None:
    if report is None:
        return None
    return {
        "status": report.status,
        "score": report.score,
        "report_path": report.report_path,
        "issues": [issue.model_dump(mode="json") for issue in report.issues],
    }


def build_retry_cache(outputs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    for output in outputs:
        source_video = output.get("source_video")
        if not source_video:
            continue
        try:
            cache[str(Path(source_video).expanduser().resolve()).lower()] = output
        except OSError:
            cache[str(source_video)] = output
    return cache


def _retry_history(
    cached_output: dict[str, Any],
    settings: DouyinReupSettings,
    retried_at: str,
) -> list[dict[str, str | None]]:
    history = [
        dict(item)
        for item in (cached_output.get("retry_history") or [])
        if isinstance(item, dict)
    ]
    previous_preset_id = cached_output.get("preset_id")
    if previous_preset_id and previous_preset_id != settings.preset_id:
        history.append(
            {
                "from_preset_id": str(previous_preset_id),
                "from_preset_name": cached_output.get("preset_name"),
                "to_preset_id": settings.preset_id,
                "to_preset_name": settings.preset_name,
                "retried_at": retried_at,
            }
        )
    return history


def _existing_cached_path(value: Any) -> str | None:
    if not value:
        return None
    try:
        path = Path(str(value)).expanduser().resolve()
    except OSError:
        return None
    if path.exists() and path.is_file() and path.stat().st_size > 0:
        return str(path)
    return None


def _round_durations(durations: dict[str, float]) -> dict[str, float]:
    return {key: round(max(0.0, float(value)), 3) for key, value in durations.items()}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _friendly_error(message: str) -> str:
    text = " ".join(str(message).split())
    lowered = text.lower()
    if "faster-whisper" in lowered or "faster_whisper" in lowered:
        return "Không tìm thấy faster-whisper. Hãy cài dependency bằng `py -m pip install -r backend/requirements.txt` hoặc tắt ASR."
    if "easyocr" in lowered:
        return "EasyOCR chưa sẵn sàng. Auto Tool sẽ tự cài/tải OCR dependency khi mở app; đợi vài phút rồi retry video lỗi."
    if "paddleocr" in lowered or "paddlepaddle" in lowered:
        return "PaddleOCR chưa sẵn sàng hoặc paddlepaddle không hỗ trợ Python hiện tại. Auto Tool mặc định dùng EasyOCR cho OCR hard-sub."
    if "permission" in lowered or "access is denied" in lowered:
        return "Không có quyền đọc/ghi file hoặc thư mục output. Hãy chọn thư mục khác hoặc cấp quyền ghi."
    if "no such file" in lowered or "not found" in lowered or "không tìm thấy" in lowered:
        return text
    if "ffmpeg" in lowered:
        return f"Render FFmpeg lỗi: {text}"
    if "gemini" in lowered or "translation" in lowered or "dịch" in lowered:
        return f"Dịch subtitle lỗi: {text}"
    return text or "Video thất bại nhưng không có thông báo lỗi chi tiết."
