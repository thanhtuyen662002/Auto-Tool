from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.adapters.gemini_adapter import GeminiAdapter
from app.modules.subtitle_quality.subtitle_quality_schema import SubtitleLineQualityScore
from app.modules.subtitle_quality.subtitle_quality_scorer import SubtitleQualityScorer
from app.modules.subtitle_quality.subtitle_quality_service import SubtitleQualityService
from app.modules.subtitle_review.subtitle_review_repository import SubtitleReviewRepository
from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine, SubtitleReviewStatus
from app.modules.subtitle_review.subtitle_validation_service import SubtitleValidationService
from app.modules.subtitle_rewrite.subtitle_rewrite_prompt_builder import build_subtitle_rewrite_prompt
from app.modules.subtitle_rewrite.subtitle_rewrite_repository import SubtitleRewriteRepository
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import (
    ApplySubtitleRewriteRequest,
    BulkRewriteFlaggedLinesRequest,
    BulkSubtitleRewriteResponse,
    GenerateSubtitleRewriteRequest,
    SubtitleRewriteStyle,
    SubtitleRewriteSuggestion,
)
from app.modules.subtitle_rewrite.subtitle_rewrite_validator import SubtitleRewriteValidator
from app.utils.file_utils import write_json


FILLER_PATTERNS = (
    r"\bthật sự\b",
    r"\bcực kỳ\b",
    r"\brất là\b",
    r"\bnói chung là\b",
    r"\bcác bạn có thể thấy\b",
    r"\bmình thấy là\b",
)

PHRASE_REPLACEMENTS = (
    (r"\bcó thể giúp bạn\b", "giúp bạn"),
    (r"\brất tiện lợi khi sử dụng\b", "dùng tiện"),
    (r"\bsản phẩm này\b", "món này"),
)


class SubtitleRewriteService:
    def __init__(
        self,
        repository: SubtitleRewriteRepository | None = None,
        review_repository: SubtitleReviewRepository | None = None,
        quality_service: SubtitleQualityService | None = None,
        validator: SubtitleRewriteValidator | None = None,
        line_validator: SubtitleValidationService | None = None,
        scorer: SubtitleQualityScorer | None = None,
        gemini_adapter: GeminiAdapter | None = None,
    ) -> None:
        self.repository = repository or SubtitleRewriteRepository()
        self.review_repository = review_repository or SubtitleReviewRepository()
        self.quality_service = quality_service or SubtitleQualityService(review_repository=self.review_repository)
        self.validator = validator or SubtitleRewriteValidator()
        self.line_validator = line_validator or SubtitleValidationService()
        self.scorer = scorer or SubtitleQualityScorer()
        self.gemini_adapter = gemini_adapter

    def generate_suggestions_for_line(
        self,
        document_id: str,
        line_index: int,
        request: GenerateSubtitleRewriteRequest,
    ) -> list[SubtitleRewriteSuggestion]:
        document = self.review_repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        line = next((item for item in document.lines if item.index == line_index), None)
        if line is None:
            raise LookupError(f"Subtitle line not found: {line_index}")

        quality_report = self.quality_service.get_quality_report(document_id)
        quality = next((item for item in quality_report.lines if item.line_index == line_index), None)
        current_text = _current_text(line)
        keywords = _preserve_keywords(document.project_id, current_text, request.preserve_keywords)
        max_chars = _target_max_chars(line, quality, request.max_chars, request.style)
        raw_suggestions: list[dict[str, str]] = []
        fallback_warning: str | None = None

        if request.use_ai:
            try:
                adapter = self.gemini_adapter or _build_gemini_adapter(document.project_id)
                payload = adapter.generate_json(
                    build_subtitle_rewrite_prompt(
                        source_text=line.source_text,
                        original_translation=current_text,
                        issues=quality.issues if quality else [],
                        style=request.style,
                        suggestion_count=request.suggestion_count,
                        max_chars=max_chars,
                        preserve_keywords=keywords,
                    )
                )
                raw_suggestions = _parse_ai_suggestions(payload, request.suggestion_count)
                if not raw_suggestions:
                    raise ValueError("Gemini returned no rewrite suggestions.")
            except Exception:
                fallback_warning = "AI rewrite unavailable, used rule-based fallback."
        else:
            fallback_warning = "AI rewrite unavailable, used rule-based fallback."

        if not raw_suggestions:
            raw_suggestions = [
                {
                    "text": rule_based_shorten_vietnamese(current_text, max_chars=max_chars),
                    "reason": "Rule-based shortening removed filler and simplified common phrases.",
                }
            ]

        created_at = _now()
        suggestions: list[SubtitleRewriteSuggestion] = []
        seen: set[str] = set()
        for item in raw_suggestions:
            suggested_text = " ".join(str(item.get("text") or "").strip().split())
            if suggested_text.casefold() in seen:
                continue
            seen.add(suggested_text.casefold())
            _, safety_warnings = self.validator.validate_suggestion(
                line.source_text,
                current_text,
                suggested_text,
                keywords,
            )
            if fallback_warning:
                safety_warnings.append(fallback_warning)
            after = self._score_suggestion(document.lines, line, suggested_text, quality, document.source_type)
            duration_seconds = max(0.001, (line.end_ms - line.start_ms) / 1000)
            suggestions.append(
                SubtitleRewriteSuggestion(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    line_index=line_index,
                    source_text=line.source_text,
                    original_translation=current_text,
                    suggested_text=suggested_text,
                    style=request.style,
                    reason=str(item.get("reason") or "Shorter and easier to read.").strip(),
                    char_count_before=len(current_text.replace("\n", "").strip()),
                    char_count_after=len(suggested_text.replace("\n", "").strip()),
                    estimated_cps_before=round(len(current_text.replace("\n", "").strip()) / duration_seconds, 3),
                    estimated_cps_after=round(len(suggested_text.replace("\n", "").strip()) / duration_seconds, 3),
                    safety_warnings=list(dict.fromkeys(safety_warnings)),
                    quality_score_before=quality.score if quality else line.quality_score,
                    quality_score_after=after.score,
                    created_at=created_at,
                )
            )

        saved = self.repository.create_many(suggestions)
        self._write_log(document_id, request_increment=1)
        return saved

    def apply_suggestion(
        self,
        document_id: str,
        line_index: int,
        request: ApplySubtitleRewriteRequest,
        *,
        auto_applied: bool = False,
    ) -> SubtitleLine:
        suggestion = self.repository.get(request.suggestion_id)
        if suggestion is None or suggestion.document_id != document_id or suggestion.line_index != line_index:
            raise LookupError(f"Subtitle rewrite suggestion not found: {request.suggestion_id}")
        document = self.review_repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        line = next((item for item in document.lines if item.index == line_index), None)
        if line is None:
            raise LookupError(f"Subtitle line not found: {line_index}")
        if _current_text(line) != suggestion.original_translation:
            raise ValueError("Subtitle line changed after this suggestion was generated. Generate suggestions again.")
        if auto_applied and not _auto_apply_eligible(suggestion):
            raise ValueError("Suggestion does not meet safe auto-apply requirements.")

        history = [
            *line.rewrite_history,
            {
                "rewrite_applied": True,
                "suggestion_id": suggestion.id,
                "quality_score_before": suggestion.quality_score_before,
                "quality_score_after": suggestion.quality_score_after,
                "auto_applied": auto_applied,
                "applied_at": _now(),
            },
        ]
        updated_line = self.line_validator.validate_line(
            line.model_copy(
                update={
                    "edited_text": suggestion.suggested_text,
                    "status": SubtitleReviewStatus.reviewed,
                    "rewrite_history": history,
                }
            )
        )
        lines = [updated_line if item.index == line_index else item for item in document.lines]
        updated_document = self.line_validator.validate_document(
            document.model_copy(update={"lines": lines, "updated_at": _now()})
        )
        self.review_repository.update_document(updated_document)
        if request.refresh_quality_score:
            self.quality_service.refresh_quality_report(document_id)
        self.repository.mark_applied(suggestion.id, _now(), auto_applied=auto_applied)
        self._write_log(document_id)
        refreshed = self.review_repository.get(document_id)
        assert refreshed is not None
        return next(item for item in refreshed.lines if item.index == line_index)

    def generate_suggestions_for_flagged_lines(
        self,
        document_id: str,
        request: BulkRewriteFlaggedLinesRequest,
    ) -> BulkSubtitleRewriteResponse:
        document = self.review_repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        report = self.quality_service.get_quality_report(document_id)
        issue_filter = {item.strip() for item in request.only_issue_types if item.strip()}
        candidates = [
            line
            for line in report.lines
            if line.needs_review
            and (not issue_filter or issue_filter.intersection(issue.issue_type.value for issue in line.issues))
        ][: request.max_lines]

        items: list[SubtitleRewriteSuggestion] = []
        auto_applied_count = 0
        for quality_line in candidates:
            suggestions = self.generate_suggestions_for_line(
                document_id,
                quality_line.line_index,
                GenerateSubtitleRewriteRequest(
                    style=request.style,
                    suggestion_count=3,
                    use_ai=True,
                ),
            )
            items.extend(suggestions)
            if request.auto_apply_safe_suggestions:
                eligible = sorted(
                    (item for item in suggestions if _auto_apply_eligible(item)),
                    key=lambda item: item.quality_score_after or 0,
                    reverse=True,
                )
                if eligible:
                    self.apply_suggestion(
                        document_id,
                        quality_line.line_index,
                        ApplySubtitleRewriteRequest(suggestion_id=eligible[0].id),
                        auto_applied=True,
                    )
                    auto_applied_count += 1

        return BulkSubtitleRewriteResponse(
            processed_lines=len(candidates),
            suggestions_created=len(items),
            auto_applied=auto_applied_count,
            items=items,
        )

    def _score_suggestion(
        self,
        lines: list[SubtitleLine],
        line: SubtitleLine,
        suggested_text: str,
        current_quality: SubtitleLineQualityScore | None,
        source_type: str | None,
    ) -> SubtitleLineQualityScore:
        position = next(index for index, item in enumerate(lines) if item.index == line.index)
        return self.scorer.score_line(
            line.model_copy(update={"edited_text": suggested_text}),
            previous_line=lines[position - 1] if position > 0 else None,
            next_line=lines[position + 1] if position + 1 < len(lines) else None,
            source_type=source_type,
            ocr_confidence=current_quality.ocr_confidence if current_quality else None,
            asr_confidence=current_quality.asr_confidence if current_quality else None,
        )

    def _write_log(self, document_id: str, *, request_increment: int = 0) -> None:
        document = self.review_repository.get(document_id)
        if document is None:
            return
        path = Path(document.translated_srt_path).parent / "subtitle_rewrite_log.json"
        previous: dict[str, Any] = {}
        try:
            previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            previous = {}
        stats = self.repository.stats_for_documents([document_id])
        suggestions = self.repository.list_for_document(document_id)
        warnings = list(dict.fromkeys(warning for item in suggestions for warning in item.safety_warnings))
        applied_items = [
            {
                "line_index": item.line_index,
                "suggestion_id": item.id,
                "auto_applied": item.auto_applied,
                "quality_score_before": item.quality_score_before,
                "quality_score_after": item.quality_score_after,
                "applied_at": item.applied_at,
            }
            for item in suggestions
            if item.applied_at
        ]
        write_json(
            path,
            {
                "document_id": document_id,
                "total_requests": int(previous.get("total_requests", 0)) + request_increment,
                "suggestions_created": stats["suggestions_created"],
                "suggestions_applied": stats["suggestions_applied"],
                "auto_applied": stats["auto_applied"],
                "average_score_before": stats["average_score_before"],
                "average_score_after": stats["average_score_after"],
                "average_quality_improvement": stats["average_quality_improvement"],
                "applied_items": applied_items,
                "warnings": warnings,
            },
        )


def rule_based_shorten_vietnamese(text: str, max_chars: int | None = None) -> str:
    result = " ".join(text.strip().split())
    for pattern in FILLER_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    for pattern, replacement in PHRASE_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    result = re.sub(r"\s+([,.;!?])", r"\1", result)
    result = re.sub(r"\s{2,}", " ", result).strip(" ,;-:")
    if max_chars and len(result) > max_chars:
        clauses = [part.strip() for part in re.split(r"(?<=[.!?])\s+|[,;:]\s*", result) if part.strip()]
        selected: list[str] = []
        for clause in clauses:
            candidate = ", ".join([*selected, clause])
            if len(candidate) > max_chars:
                break
            selected.append(clause)
        if selected:
            result = ", ".join(selected)
        elif " " in result[: max_chars + 1]:
            result = result[: max_chars + 1].rsplit(" ", 1)[0].rstrip(" ,;-:")
    return result or text.strip()


def _current_text(line: SubtitleLine) -> str:
    return ((line.edited_text if line.edited_text is not None else line.translated_text) or "").strip()


def _parse_ai_suggestions(payload: dict[str, Any], limit: int) -> list[dict[str, str]]:
    items = payload.get("suggestions")
    if not isinstance(items, list):
        return []
    parsed: list[dict[str, str]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            parsed.append({"text": text, "reason": str(item.get("reason") or "").strip()})
    return parsed


def _target_max_chars(
    line: SubtitleLine,
    quality: SubtitleLineQualityScore | None,
    requested: int | None,
    style: SubtitleRewriteStyle,
) -> int | None:
    current_length = len(_current_text(line).replace("\n", ""))
    limits = [requested] if requested else []
    issue_types = {issue.issue_type.value for issue in quality.issues} if quality else set()
    if "too_long" in issue_types:
        limits.append(min(int(current_length * 0.75), 56))
    if "reading_speed_too_high" in issue_types:
        duration_seconds = max(0.1, (line.end_ms - line.start_ms) / 1000)
        limits.append(max(8, int(18 * duration_seconds)))
    if style == SubtitleRewriteStyle.very_short:
        limits.append(min(40, max(8, int(current_length * 0.6))))
    elif style == SubtitleRewriteStyle.casual_tiktok:
        limits.append(min(52, max(8, int(current_length * 0.8))))
    return min(limit for limit in limits if limit is not None) if limits else None


def _build_gemini_adapter(project_id: str | None) -> GeminiAdapter:
    api_keys: list[str] = []
    model_name = "gemini-3.1-flash-lite"
    if project_id:
        project = database.get_project(project_id)
        config = project.get("config", {}) if project else {}
        ai = config.get("ai", {}) if isinstance(config, dict) else {}
        if isinstance(ai, dict):
            api_keys = list(ai.get("gemini_api_keys") or [])
            model_name = str(ai.get("text_model") or model_name)
    return GeminiAdapter(api_key=None, model_name=model_name, api_keys=api_keys, timeout_seconds=45)


def _preserve_keywords(project_id: str | None, text: str, requested: list[str]) -> list[str]:
    keywords = list(requested)
    if project_id:
        project = database.get_project(project_id)
        config = project.get("config", {}) if project else {}
        product = config.get("product", {}) if isinstance(config, dict) else {}
        if isinstance(product, dict):
            for field in ("brand", "name"):
                value = str(product.get(field) or "").strip()
                if value and value.casefold() in text.casefold():
                    keywords.append(value)
    return list(dict.fromkeys(keyword for keyword in keywords if keyword))


def _auto_apply_eligible(suggestion: SubtitleRewriteSuggestion) -> bool:
    return (
        not suggestion.safety_warnings
        and (suggestion.quality_score_after or 0) >= 0.85
        and suggestion.char_count_after < suggestion.char_count_before
    )


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
