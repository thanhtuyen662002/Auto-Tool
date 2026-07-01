from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.modules.douyin_reup.douyin_schema import DouyinOutputResult, DouyinReupSummary
from app.schemas.project_schema import ProjectConfig


def build_douyin_reup_summary(
    *,
    config: ProjectConfig,
    output_root: Path,
    outputs: list[DouyinOutputResult],
    subtitle_sources: dict[str, int] | None = None,
    scan_seconds: float = 0.0,
    total_runtime_seconds: float = 0.0,
) -> DouyinReupSummary:
    failures = [output for output in outputs if output.status == "failed"]
    needs_review = [output for output in outputs if output.status == "needs_review"]
    rendered = [output for output in outputs if output.status == "success" and output.path]
    successful_outputs = len([output for output in outputs if output.status in {"success", "needs_review"}])
    failure_breakdown = _failure_breakdown(failures)
    performance = _performance(outputs, scan_seconds=scan_seconds, total_runtime_seconds=total_runtime_seconds)
    ocr_summary = _ocr_summary(outputs)
    gpu_acceleration = _gpu_acceleration_summary(outputs)
    subtitle_quality = _subtitle_quality_summary(outputs)
    settings = config.douyin_reup
    subtitle_rewrite = _subtitle_rewrite_summary(
        outputs,
        enabled=bool(settings.enable_subtitle_rewrite_suggestions) if settings else False,
    )
    final_output_qa = _final_output_qa_summary(outputs)

    return DouyinReupSummary(
        project_name=config.project_name,
        output_folder=str(output_root),
        total_videos=len(outputs),
        processed_outputs=len(outputs),
        successful_outputs=successful_outputs,
        failed_outputs=len(failures),
        warnings_count=sum(len(output.warnings) for output in outputs),
        subtitle_sources=subtitle_sources or dict(Counter(output.subtitle_source or "none" for output in outputs)),
        failed_items=[
            {
                "index": output.index,
                "reason": (output.error_message or "; ".join(output.errors))[:300],
                "failed_step": output.failed_step or "unknown",
            }
            for output in failures
        ],
        outputs=outputs,
        subtitle_review={
            "enabled": bool(settings.review_subtitles_before_render) if settings else True,
            "documents_created": len([output for output in outputs if output.subtitle_review_document_id]),
            "approved": 0,
            "pending": len(needs_review),
        },
        silent_immersive=_silent_immersive_summary(outputs, settings),
        silent_caption_templates=_silent_caption_template_summary(outputs),
        silent_visual_tagging=_silent_visual_tagging_summary(outputs),
        success=successful_outputs,
        failed=len(failures),
        needs_review=len(needs_review),
        rendered=len(rendered),
        failure_breakdown=failure_breakdown,
        performance=performance,
        gpu_acceleration=gpu_acceleration,
        ocr_summary=ocr_summary,
        preset=_preset_summary(settings),
        settings_snapshot=settings.model_dump(mode="json") if settings else {},
        subtitle_quality=subtitle_quality,
        subtitle_rewrite=subtitle_rewrite,
        final_output_qa=final_output_qa,
    )


def _failure_breakdown(outputs: list[DouyinOutputResult]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for output in outputs:
        step = (output.failed_step or "unknown").strip().lower()
        key = {
            "subtitle_source": "asr_failed",
            "detect_subtitle_source": "asr_failed",
            "asr": "asr_failed",
            "translation": "translation_failed",
            "translate_subtitle": "translation_failed",
            "render": "render_failed",
            "render_final_video": "render_failed",
            "review_document": "review_document_failed",
            "ocr": "ocr_failed",
            "ocr_hardsub": "ocr_failed",
        }.get(step, f"{step}_failed" if step else "unknown_failed")
        counter[key] += 1
    return dict(counter)


def _performance(
    outputs: list[DouyinOutputResult],
    *,
    scan_seconds: float,
    total_runtime_seconds: float,
) -> dict[str, float | str]:
    averages = {
        "asr": _average_duration(outputs, "asr_seconds"),
        "ocr": _average_duration(outputs, "ocr_seconds"),
        "translation": _average_duration(outputs, "translation_seconds"),
        "render": _average_duration(outputs, "render_seconds"),
    }
    slowest_step = max(averages, key=lambda key: averages[key]) if any(averages.values()) else "scan"
    return {
        "scan_seconds": round(max(0.0, scan_seconds), 3),
        "average_asr_seconds_per_video": round(averages["asr"], 3),
        "average_ocr_seconds_per_video": round(averages["ocr"], 3),
        "average_translation_seconds_per_video": round(averages["translation"], 3),
        "average_render_seconds_per_video": round(averages["render"], 3),
        "total_runtime_seconds": round(max(0.0, total_runtime_seconds), 3),
        "slowest_step": slowest_step,
    }


def _average_duration(outputs: list[DouyinOutputResult], key: str) -> float:
    values = [float(output.durations.get(key, 0.0)) for output in outputs if output.durations.get(key)]
    return sum(values) / len(values) if values else 0.0


def _ocr_summary(outputs: list[DouyinOutputResult]) -> dict[str, int | float]:
    attempted = [output for output in outputs if output.ocr_frame_count or output.subtitle_source == "ocr_hardsub"]
    successes = [output for output in attempted if output.subtitle_source == "ocr_hardsub" and output.ocr_detected_line_count > 0]
    confidences = [output.ocr_average_confidence for output in successes if output.ocr_average_confidence > 0]
    return {
        "videos_attempted": len(attempted),
        "videos_success": len(successes),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
    }


def _preset_summary(settings: Any) -> dict[str, str | None]:
    if not settings:
        return {"id": None, "name": None}
    return {
        "id": getattr(settings, "preset_id", None),
        "name": getattr(settings, "preset_name", None),
    }


def _subtitle_quality_summary(outputs: list[DouyinOutputResult]) -> dict[str, Any]:
    gate_scores = [output.subtitle_quality_score for output in outputs if output.subtitle_quality_score > 0]
    rejected = [item for output in outputs for item in output.subtitle_rejected_sources]
    document_ids = [
        output.subtitle_review_document_id
        for output in outputs
        if output.subtitle_review_document_id
    ]
    if not document_ids:
        return {
            "average_score": 0.0,
            "documents_with_critical": 0,
            "total_flagged_lines": 0,
            "average_source_quality_score": round(sum(gate_scores) / len(gate_scores), 4) if gate_scores else 0.0,
            "rejected_source_count": len(rejected),
            "rejected_source_breakdown": dict(Counter(str(item.get("source") or "unknown") for item in rejected)),
        }
    try:
        from app.modules.subtitle_quality.subtitle_quality_repository import SubtitleQualityRepository

        reports = SubtitleQualityRepository().list_by_document_ids(document_ids)
    except Exception:
        reports = []
    return {
        "average_score": round(sum(report.average_score for report in reports) / len(reports), 4) if reports else 0.0,
        "documents_with_critical": sum(1 for report in reports if report.critical_count > 0),
        "total_flagged_lines": sum(report.needs_review_count for report in reports),
        "average_source_quality_score": round(sum(gate_scores) / len(gate_scores), 4) if gate_scores else 0.0,
        "rejected_source_count": len(rejected),
        "rejected_source_breakdown": dict(Counter(str(item.get("source") or "unknown") for item in rejected)),
    }


def _gpu_acceleration_summary(outputs: list[DouyinOutputResult]) -> dict[str, Any]:
    profiles = [getattr(output, "gpu_profile", None) for output in outputs]
    profiles = [profile for profile in profiles if isinstance(profile, dict)]
    encoder_counts = Counter(str(profile.get("render_encoder") or "unknown") for profile in profiles)
    nvenc_count = sum(1 for profile in profiles if profile.get("render_nvenc_used"))
    asr_cuda_count = sum(1 for profile in profiles if profile.get("asr_cuda_used"))
    ocr_gpu_ready_count = sum(1 for profile in profiles if profile.get("ocr_gpu_ready"))
    readiness = next((profile.get("readiness") for profile in profiles if isinstance(profile.get("readiness"), dict)), {})
    return {
        "safe_cpu_fallback": True,
        "profiled_videos": len(profiles),
        "render_nvenc_videos": nvenc_count,
        "render_cpu_videos": max(0, len(profiles) - nvenc_count),
        "asr_cuda_videos": asr_cuda_count,
        "ocr_gpu_ready_videos": ocr_gpu_ready_count,
        "encoder_counts": dict(encoder_counts),
        "readiness": readiness,
    }


def _subtitle_rewrite_summary(outputs: list[DouyinOutputResult], *, enabled: bool) -> dict[str, int | float | bool]:
    document_ids = [
        output.subtitle_review_document_id
        for output in outputs
        if output.subtitle_review_document_id
    ]
    try:
        from app.modules.subtitle_rewrite.subtitle_rewrite_repository import SubtitleRewriteRepository

        stats = SubtitleRewriteRepository().stats_for_documents(document_ids)
    except Exception:
        stats = {
            "suggestions_created": 0,
            "suggestions_applied": 0,
            "auto_applied": 0,
            "average_quality_improvement": 0.0,
        }
    return {
        "enabled": enabled,
        "suggestions_created": stats["suggestions_created"],
        "suggestions_applied": stats["suggestions_applied"],
        "average_quality_improvement": stats["average_quality_improvement"],
    }


def _final_output_qa_summary(outputs: list[DouyinOutputResult]) -> dict[str, Any]:
    reports = [output.final_output_qa for output in outputs if output.final_output_qa]
    issues = [issue for report in reports for issue in (report.get("issues") or []) if isinstance(issue, dict)]
    return {
        "platform_target": "tiktok",
        "total_checked": len(reports),
        "passed": sum(1 for report in reports if report.get("status") == "passed"),
        "passed_with_warnings": sum(1 for report in reports if report.get("status") == "passed_with_warnings"),
        "failed": sum(1 for report in reports if report.get("status") == "failed"),
        "average_score": round(sum(float(report.get("score") or 0) for report in reports) / len(reports), 4) if reports else 0.0,
        "issue_breakdown": dict(Counter(str(issue.get("issue_type") or "unknown") for issue in issues)),
    }


def _silent_immersive_summary(outputs: list[DouyinOutputResult], settings: Any) -> dict[str, Any]:
    silent_outputs = [output for output in outputs if getattr(output, "reup_mode", None) == "silent_immersive"]
    strategies = Counter(getattr(output, "silent_strategy", None) or "unknown" for output in silent_outputs)
    caption_sources = Counter(getattr(output, "caption_source", None) or "unknown" for output in silent_outputs)
    return {
        "enabled": bool(getattr(settings, "enable_silent_immersive_mode", False)) if settings else False,
        "videos_detected_silent": len(silent_outputs),
        "videos_processed_silent": len([output for output in silent_outputs if output.status in {"success", "needs_review"}]),
        "strategies": dict(strategies),
        "caption_sources": dict(caption_sources),
    }


def _silent_caption_template_summary(outputs: list[DouyinOutputResult]) -> dict[str, Any]:
    metadata = [
        output.silent_caption_generation
        for output in outputs
        if output.silent_caption_generation
    ]
    industries = Counter(str(item.get("industry") or "general_product") for item in metadata)
    scores = [float(item.get("average_quality_score") or 0.0) for item in metadata]
    return {
        "industry_usage": dict(industries),
        "average_caption_quality_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "regenerated_count": sum(int(item.get("regeneration_count") or 0) for item in metadata),
    }


def _silent_visual_tagging_summary(outputs: list[DouyinOutputResult]) -> dict[str, Any]:
    metadata = [output.silent_visual_tagging for output in outputs if output.silent_visual_tagging]
    industries = Counter(str(item.get("recommended_industry") or "general_product") for item in metadata)
    confidences = [float(item.get("average_confidence") or 0.0) for item in metadata]
    return {
        "videos_tagged": len(metadata),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "recommended_industries": dict(industries),
    }
