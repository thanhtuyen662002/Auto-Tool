from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.adapters.ffmpeg_adapter import probe_video
from app.modules.output_review.review_schema import (
    OutputQualityScore,
    OutputReviewStatus,
    OutputReviewSummary,
)
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json


class OutputQualityReviewService:
    def analyze_output(self, project_id: str, output_index: int) -> OutputQualityScore:
        project = database.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        config = ProjectConfig.model_validate(project["config"])
        output = _latest_outputs_by_index(project_id).get(output_index)
        if not output:
            raise ValueError(f"Output {output_index} was not found for project {project_id}")

        score = self._score_output(config, output)
        existing = database.get_output_review(project_id, output_index)
        review_status = existing["review_status"] if existing else OutputReviewStatus.pending.value
        user_note = existing.get("user_note") if existing else None
        database.upsert_output_review(
            project_id=project_id,
            output_index=output_index,
            review_status=review_status,
            user_note=user_note,
            quality_score=score.model_dump(mode="json"),
        )
        return score

    def analyze_project_outputs(self, project_id: str) -> list[OutputQualityScore]:
        project = database.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        config = ProjectConfig.model_validate(project["config"])
        outputs = _latest_outputs_by_index(project_id)
        scores = [self._score_output(config, outputs[index]) for index in sorted(outputs)]

        for score in scores:
            existing = database.get_output_review(project_id, score.output_index)
            database.upsert_output_review(
                project_id=project_id,
                output_index=score.output_index,
                review_status=existing["review_status"] if existing else OutputReviewStatus.pending.value,
                user_note=existing.get("user_note") if existing else None,
                quality_score=score.model_dump(mode="json"),
            )

        self.write_review_file(project_id, project, scores)
        return scores

    def build_summary(self, scores: list[OutputQualityScore]) -> OutputReviewSummary:
        total = len(scores)
        if total == 0:
            return OutputReviewSummary(
                total_outputs=0,
                good=0,
                review=0,
                needs_rerender=0,
                failed=0,
                bad=0,
                average_overall_score=0.0,
            )

        return OutputReviewSummary(
            total_outputs=total,
            good=sum(1 for score in scores if score.recommended_action == "good"),
            review=sum(1 for score in scores if score.recommended_action == "review"),
            needs_rerender=sum(1 for score in scores if score.recommended_action == "needs_rerender"),
            failed=sum(1 for score in scores if score.recommended_action == "rerender_failed"),
            bad=sum(1 for score in scores if score.recommended_action == "bad"),
            average_overall_score=round(sum(score.overall_score for score in scores) / total, 3),
        )

    def write_review_file(
        self,
        project_id: str,
        project: dict[str, Any],
        scores: list[OutputQualityScore],
    ) -> str:
        config = ProjectConfig.model_validate(project["config"])
        output_dir = _latest_output_folder(project_id) or Path(config.output_folder)
        output_dir = ensure_dir(output_dir)
        summary = self.build_summary(scores)
        payload = {
            "project_id": project_id,
            "project_name": config.project_name,
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "summary": summary.model_dump(mode="json"),
            "outputs": [
                {
                    "output_index": score.output_index,
                    "final_video_path": score.final_video_path,
                    "overall_score": score.overall_score,
                    "recommended_action": score.recommended_action,
                    "warnings": score.warnings,
                    "errors": score.errors,
                }
                for score in scores
            ],
        }
        review_path = output_dir / "output_quality_review.json"
        write_json(review_path, payload)
        return str(review_path)

    def _score_output(self, config: ProjectConfig, output: dict[str, Any]) -> OutputQualityScore:
        output_index = int(output.get("index") or 0)
        final_video_path = str(output.get("path") or "")
        status = str(output.get("status") or "unknown")
        log_payload = _read_json(output.get("log_file"))
        timeline_payload = _read_json(output.get("timeline_file"))
        qa_payload = _qa_payload(output, log_payload)
        warnings = _short_unique(_as_list(output.get("warnings")) + _as_list(log_payload.get("warnings")) + _as_list(qa_payload.get("warnings")))
        errors = _short_unique(_as_list(output.get("errors")) + _as_list(log_payload.get("errors")) + _as_list(qa_payload.get("errors")))
        if output.get("error"):
            errors = _short_unique([str(output["error"]), *errors])

        technical_score = _technical_score(final_video_path, status, qa_payload, warnings, errors, config)
        segment_score = _segment_score(output, log_payload, timeline_payload)
        audio_score = _audio_score(output, log_payload, qa_payload, config)
        subtitle_score = _subtitle_score(output, log_payload, qa_payload, warnings)
        timeline_score = _timeline_score(output, log_payload, timeline_payload)

        overall_score = round(
            technical_score * 0.30
            + segment_score * 0.25
            + audio_score * 0.20
            + subtitle_score * 0.15
            + timeline_score * 0.10,
            3,
        )
        recommended_action = _recommended_action(status, overall_score)

        return OutputQualityScore(
            output_index=output_index,
            final_video_path=final_video_path,
            status=status,
            technical_score=technical_score,
            segment_score=segment_score,
            audio_score=audio_score,
            subtitle_score=subtitle_score,
            timeline_score=timeline_score,
            overall_score=overall_score,
            warnings=warnings,
            errors=errors,
            recommended_action=recommended_action,
        )


def build_review_rows(project_id: str, scores: list[OutputQualityScore]) -> list[dict[str, Any]]:
    reviews = {item["output_index"]: item for item in database.list_output_reviews(project_id)}
    rows: list[dict[str, Any]] = []
    for score in scores:
        review = reviews.get(score.output_index, {})
        rows.append(
            {
                "output_index": score.output_index,
                "video_path": score.final_video_path,
                "status": score.status,
                "overall_score": score.overall_score,
                "technical_score": score.technical_score,
                "segment_score": score.segment_score,
                "audio_score": score.audio_score,
                "subtitle_score": score.subtitle_score,
                "timeline_score": score.timeline_score,
                "recommended_action": score.recommended_action,
                "review_status": review.get("review_status", OutputReviewStatus.pending.value),
                "user_note": review.get("user_note"),
                "warnings": score.warnings,
                "errors": score.errors,
            }
        )
    return rows


def latest_outputs_for_project(project_id: str) -> dict[int, dict[str, Any]]:
    return _latest_outputs_by_index(project_id)


def _latest_outputs_by_index(project_id: str) -> dict[int, dict[str, Any]]:
    outputs: dict[int, dict[str, Any]] = {}
    for job in database.get_project_jobs(project_id, include_preview=False):
        for output in job.get("results", {}).get("outputs", []):
            if not isinstance(output, dict):
                continue
            try:
                index = int(output["index"])
            except (KeyError, TypeError, ValueError):
                continue
            outputs[index] = output
    return outputs


def _latest_output_folder(project_id: str) -> Path | None:
    jobs = database.get_project_jobs(project_id, include_preview=False)
    for job in reversed(jobs):
        output_folder = job.get("output_folder")
        if output_folder:
            return Path(output_folder)
    return None


def _technical_score(
    final_video_path: str,
    status: str,
    qa_payload: dict[str, Any],
    warnings: list[str],
    errors: list[str],
    config: ProjectConfig,
) -> float:
    if status == "failed":
        return 0.0
    if qa_payload:
        if qa_payload.get("errors"):
            return 0.45
        score = 1.0
        if qa_payload.get("warnings"):
            score -= min(0.25, len(qa_payload["warnings"]) * 0.08)
        for key in ("exists", "probe_ok", "duration_ok", "resolution_ok", "has_video_stream"):
            if qa_payload.get(key) is False:
                score -= 0.15
        if errors:
            score -= 0.3
        elif warnings:
            score -= min(0.15, len(warnings) * 0.04)
        return _clip(score)

    path = Path(final_video_path)
    if not path.exists() or path.stat().st_size <= 0:
        return 0.0
    try:
        media = probe_video(str(path))
    except Exception:
        return 0.0
    expected_width, expected_height = _resolution(config.render.resolution)
    score = 1.0
    if (media.width, media.height) != (expected_width, expected_height):
        score -= 0.25
    if abs(media.duration - config.render.duration) > 2:
        score -= 0.2
    if not media.has_audio:
        score -= 0.2
    return _clip(score)


def _segment_score(output: dict[str, Any], log_payload: dict[str, Any], timeline_payload: dict[str, Any]) -> float:
    average_score = _float(
        timeline_payload.get("average_segment_score")
        or log_payload.get("average_segment_score")
        or output.get("average_segment_score"),
        default=0.75,
    )
    diversity = timeline_payload.get("source_diversity") or log_payload.get("source_diversity") or {}
    unique_sources = _float(diversity.get("unique_sources"), default=0.0)
    total_clips = _float(diversity.get("total_clips"), default=0.0)
    if total_clips <= 0:
        total_clips = len(timeline_payload.get("clips") or [])
        unique_sources = len({clip.get("source_path") for clip in timeline_payload.get("clips", []) if isinstance(clip, dict)})
    diversity_score = unique_sources / total_clips if total_clips else 0.5
    diversity_score = min(1.0, diversity_score * 1.5)
    repeat_penalty = _consecutive_repeat_penalty(timeline_payload.get("clips") or [])
    return _clip(average_score * 0.75 + diversity_score * 0.25 - repeat_penalty)


def _audio_score(output: dict[str, Any], log_payload: dict[str, Any], qa_payload: dict[str, Any], config: ProjectConfig) -> float:
    if qa_payload and qa_payload.get("has_audio_stream") is False:
        return 0.0
    tts = log_payload.get("tts") if isinstance(log_payload.get("tts"), dict) else {}
    provider = str(tts.get("provider_used") or log_payload.get("tts_provider") or output.get("tts_provider") or "").lower()
    fallback_used = bool(tts.get("fallback_used") or log_payload.get("tts_fallback_used") or output.get("tts_fallback_used"))
    voice_duration = _float(tts.get("voice_duration") or log_payload.get("voice_duration") or output.get("voice_duration"), default=0.0)
    score = 1.0
    if provider in {"silent", "mock", "none"}:
        score = 0.3
    elif fallback_used:
        score = 0.8
    if voice_duration > 0:
        diff = abs(voice_duration - config.render.duration)
        if diff > 4:
            score = min(score, 0.55)
        elif diff > 2:
            score = min(score, 0.7)
    if _contains(_as_list(log_payload.get("warnings")) + _as_list(tts.get("warnings")), "voice_"):
        score = min(score, 0.75)
    return _clip(score)


def _subtitle_score(
    output: dict[str, Any],
    log_payload: dict[str, Any],
    qa_payload: dict[str, Any],
    warnings: list[str],
) -> float:
    subtitle_path = output.get("subtitle_ass_file") or output.get("subtitle_file") or log_payload.get("subtitle_ass_file") or log_payload.get("subtitle_file")
    if not subtitle_path or not Path(str(subtitle_path)).exists():
        return 0.0
    score = 1.0
    subtitle_warnings = [
        warning
        for warning in _as_list(log_payload.get("warnings")) + _as_list(qa_payload.get("warnings")) + warnings
        if "subtitle" in str(warning).lower()
    ]
    if subtitle_warnings:
        score -= min(0.3, 0.1 * len(subtitle_warnings))
    if _contains(subtitle_warnings, "burn failed"):
        score = min(score, 0.5)
    return _clip(score)


def _timeline_score(output: dict[str, Any], log_payload: dict[str, Any], timeline_payload: dict[str, Any]) -> float:
    if not timeline_payload:
        return 0.0
    clips = [clip for clip in timeline_payload.get("clips", []) if isinstance(clip, dict)]
    if not clips:
        return 0.0
    score = 1.0
    if not (timeline_payload.get("template_id") or output.get("timeline_template") or log_payload.get("timeline_template")):
        score -= 0.3
    missing_slot = sum(1 for clip in clips if not clip.get("slot_name"))
    missing_role = sum(1 for clip in clips if not clip.get("text_role"))
    missing_ratio = (missing_slot + missing_role) / max(1, len(clips) * 2)
    if missing_ratio:
        score -= min(0.45, missing_ratio * 0.6)
    return _clip(score)


def _recommended_action(status: str, overall_score: float) -> str:
    if status == "failed":
        return "rerender_failed"
    if overall_score >= 0.85:
        return "good"
    if overall_score >= 0.65:
        return "review"
    if overall_score >= 0.45:
        return "needs_rerender"
    return "bad"


def _qa_payload(output: dict[str, Any], log_payload: dict[str, Any]) -> dict[str, Any]:
    qa = log_payload.get("qa") or output.get("qa") or {}
    return qa if isinstance(qa, dict) else {}


def _read_json(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    try:
        path = Path(str(path_value))
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _short_unique(values: list[str], limit: int = 360) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned if len(cleaned) <= limit else f"{cleaned[: limit - 3]}...")
    return result


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _contains(values: list[str], needle: str) -> bool:
    needle = needle.lower()
    return any(needle in str(value).lower() for value in values)


def _consecutive_repeat_penalty(clips: list[Any]) -> float:
    if not clips:
        return 0.0
    penalty = 0.0
    previous = None
    run_length = 0
    for clip in clips:
        source = clip.get("source_path") if isinstance(clip, dict) else None
        if source and source == previous:
            run_length += 1
            if run_length >= 2:
                penalty += 0.08
        else:
            previous = source
            run_length = 1
    return min(0.25, penalty)


def _resolution(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x", 1)
    return int(width), int(height)
