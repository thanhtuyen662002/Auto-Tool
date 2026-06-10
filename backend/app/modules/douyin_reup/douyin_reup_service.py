from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

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
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_reup_service import is_silent_reup_settings
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

        _progress(progress_callback, total, completed, failed, "scanned", 5)
        for index, video in enumerate(videos, start=1):
            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}", _progress_percent(index - 1, total))
            _log(log_callback, "info", f"Đang xử lý Douyin video {index}/{total}: {video.filename}")
            try:
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
                )
                outputs.append(output)
                subtitle_sources.update([output.subtitle_source or "none"])
                if output.status in {"success", "needs_review"}:
                    completed += 1
                else:
                    failed += 1
                    _log(log_callback, "warning", f"Video {index} lỗi tại {output.failed_step or 'unknown'}: {'; '.join(output.errors)}")
            except Exception as exc:
                failed += 1
                output = self._failed_output(index, video, output_root, _friendly_error(str(exc)), settings=settings)
                outputs.append(output)
                subtitle_sources.update([output.subtitle_source or "none"])
                _log(log_callback, "error", f"Video {index} thất bại: {output.error_message or exc}")

            _progress(progress_callback, total, completed, failed, f"douyin_video_{index}_done", _progress_percent(index, total))

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
        write_json(summary_file, summary.model_dump(mode="json"))
        _progress(progress_callback, total, completed, failed, "completed", 100)
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
                source_result = self.source_detector.detect_source(video, settings, str(video_dir))
                if source_result.source_type == "asr":
                    durations["asr_seconds"] = time.perf_counter() - source_started
                    steps["asr"] = "ok"
                if source_result.source_type == "ocr_hardsub":
                    durations["ocr_seconds"] = time.perf_counter() - source_started
                    steps["ocr"] = "ok"
                warnings.extend(source_result.warnings)
                steps["subtitle_source"] = "ok"
            if source_result.source_type == "none" or not source_result.source_srt_path:
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
            render_started = time.perf_counter()
            render_payload = self.render_pipeline.render_video_with_translated_subtitle(
                video=video,
                translation_result=translation,
                settings=settings,
                output_dir=str(video_dir),
                output_name=f"douyin_{index:03d}.mp4",
            )
            durations["render_seconds"] = time.perf_counter() - render_started
            warnings.extend(render_payload.get("warnings") or [])
            errors.extend(render_payload.get("errors") or [])
            steps["render"] = "ok"
            final_qa_report = FinalOutputQAService().run_qa_for_output(
                str(render_payload["path"]),
                PlatformTarget.tiktok,
                job_id=job_id,
                project_id=project_id,
                video_id=f"douyin_{index:03d}",
                ass_path=render_payload.get("subtitle_ass_file"),
                overlay_path=render_payload.get("overlay_file"),
                subtitle_expected=settings.burn_subtitle,
                audio_expected=settings.keep_original_audio or settings.add_bgm,
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

        try:
            failed_step = "silent_plan"
            plan_started = time.perf_counter()
            plan = self.silent_pipeline.build_plan(
                video_path=video.path,
                settings=settings,
                output_dir=str(video_dir),
                product_context=_product_context(config),
            )
            durations["silent_plan_seconds"] = time.perf_counter() - plan_started
            warnings.extend(plan.warnings)
            caption_source = _silent_caption_source(plan)
            steps["silent_plan"] = "ok"

            failed_step = "silent_caption_srt"
            caption_srt_path = self.silent_pipeline.write_caption_srt(
                plan,
                str(video_dir),
                f"video_{index:03d}_silent_vi.srt",
            )
            steps["silent_caption_srt"] = "ok"

            if settings.silent_review_before_render and settings.review_subtitles_before_render and not settings.auto_render_after_translation:
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
                    voiceover_script_file=self.silent_pipeline.last_voiceover_script_path,
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
            render_started = time.perf_counter()
            render_result = self.silent_pipeline.render_from_plan(plan, settings, str(video_dir))
            durations["render_seconds"] = time.perf_counter() - render_started
            warnings.extend(render_result.warnings)
            errors.extend(render_result.errors)
            if render_result.status != "success" or not render_result.output_video_path:
                raise RuntimeError("; ".join(render_result.errors) or "Silent render không tạo được video final.")
            steps["render"] = "ok"

            final_qa_report = FinalOutputQAService().run_qa_for_output(
                render_result.output_video_path,
                PlatformTarget.tiktok,
                job_id=job_id,
                project_id=project_id,
                video_id=f"douyin_silent_{index:03d}",
                ass_path=render_result.caption_ass_path,
                overlay_path=None,
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
                voiceover_file=render_result.voiceover_path,
                voiceover_script_file=self.silent_pipeline.last_voiceover_script_path,
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
                "ocr_debug_json_path": self.silent_pipeline.last_ocr_debug_json_path,
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

    def _select_videos(self, videos: list[DouyinVideoItem], settings: DouyinReupSettings) -> list[DouyinVideoItem]:
        if settings.process_mode == "selected":
            selected = {str(Path(path).expanduser().resolve()).lower() for path in settings.selected_video_paths}
            videos = [video for video in videos if str(Path(video.path).expanduser().resolve()).lower() in selected]
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
    }


def _silent_caption_source(plan) -> str:
    if not plan or not plan.captions:
        return "template"
    sources = [caption.source for caption in plan.captions]
    if "ocr_translation" in sources:
        return "ocr_translation"
    if "visual_generated" in sources:
        return "visual_generated"
    return sources[0] if sources else "template"


def _progress(
    callback: ProgressCallback | None,
    total: int,
    completed: int,
    failed: int,
    current_step: str,
    progress: int,
) -> None:
    if not callback:
        return
    callback(
        {
            "current_step": current_step,
            "progress": progress,
            "total_outputs": total,
            "completed_outputs": completed,
            "failed_outputs": failed,
        }
    )


def _log(callback: LogCallback | None, level: str, message: str) -> None:
    if callback:
        callback(level, message)


def _progress_percent(done: int, total: int) -> int:
    if total <= 0:
        return 100
    return max(5, min(99, int((done / total) * 95) + 5))


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
