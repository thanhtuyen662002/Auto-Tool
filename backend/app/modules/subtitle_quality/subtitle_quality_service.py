from __future__ import annotations

import json
import re
from pathlib import Path

from app.modules.subtitle_quality.subtitle_quality_repository import SubtitleQualityRepository
from app.modules.subtitle_quality.subtitle_quality_schema import (
    SubtitleDocumentQualityReport,
    SubtitleQualitySeverity,
    SubtitleRewriteSuggestionResponse,
)
from app.modules.subtitle_quality.subtitle_quality_scorer import SubtitleQualityScorer
from app.modules.subtitle_review.subtitle_review_repository import SubtitleReviewRepository
from app.modules.subtitle_review.subtitle_review_schema import SubtitleReviewStatus
from app.utils.file_utils import write_json


class SubtitleQualityService:
    def __init__(
        self,
        repository: SubtitleQualityRepository | None = None,
        review_repository: SubtitleReviewRepository | None = None,
        scorer: SubtitleQualityScorer | None = None,
    ) -> None:
        self.repository = repository or SubtitleQualityRepository()
        self.review_repository = review_repository or SubtitleReviewRepository()
        self.scorer = scorer or SubtitleQualityScorer()

    def create_quality_report_for_document(
        self,
        document_id: str,
        *,
        auto_mark_low_quality_lines: bool = True,
    ) -> SubtitleDocumentQualityReport:
        return self._score_and_save(document_id, auto_mark_low_quality_lines=auto_mark_low_quality_lines)

    def get_quality_report(self, document_id: str) -> SubtitleDocumentQualityReport:
        report = self.repository.get(document_id)
        if report is None:
            return self.create_quality_report_for_document(document_id)
        return report

    def refresh_quality_report(
        self,
        document_id: str,
        *,
        auto_mark_low_quality_lines: bool = True,
    ) -> SubtitleDocumentQualityReport:
        return self._score_and_save(document_id, auto_mark_low_quality_lines=auto_mark_low_quality_lines)

    def flagged_lines(self, document_id: str):
        report = self.get_quality_report(document_id)
        return [line for line in report.lines if line.needs_review]

    def suggest_rewrite(self, document_id: str, line_index: int) -> SubtitleRewriteSuggestionResponse:
        document = self.review_repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        line = next((item for item in document.lines if item.index == line_index), None)
        if line is None:
            raise LookupError(f"Subtitle line not found: {line_index}")
        report = self.get_quality_report(document_id)
        quality = next((item for item in report.lines if item.line_index == line_index), None)
        text = (line.edited_text if line.edited_text is not None else line.translated_text) or ""
        suggestion = _shorten_rule_based(text)
        return SubtitleRewriteSuggestionResponse(
            suggestion=suggestion,
            issues=[issue.model_dump(mode="json") for issue in (quality.issues if quality else [])],
        )

    def _score_and_save(
        self,
        document_id: str,
        *,
        auto_mark_low_quality_lines: bool,
    ) -> SubtitleDocumentQualityReport:
        document = self.review_repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        report = self.scorer.score_document(
            document,
            source_type=document.source_type,
            ocr_debug=_load_debug(document.translated_srt_path, "ocr"),
            asr_debug=_load_debug(document.translated_srt_path, "asr"),
            video_duration_ms=_duration_ms(document.video_path),
        )
        report_path = Path(document.translated_srt_path).parent / "subtitle_quality_report.json"
        report = report.model_copy(update={"report_file": str(report_path)})
        saved_report = self.repository.upsert(report)
        updated_lines = []
        quality_by_index = {line.line_index: line for line in saved_report.lines}
        for line in document.lines:
            quality = quality_by_index.get(line.index)
            if not quality:
                updated_lines.append(line)
                continue
            warnings = [warning for warning in line.warnings if not warning.startswith("Quality: ")]
            warnings.extend(f"Quality: {issue.message}" for issue in quality.issues)
            status = line.status
            if auto_mark_low_quality_lines and (
                quality.score < 0.75 or quality.severity == SubtitleQualitySeverity.critical
            ):
                status = SubtitleReviewStatus.needs_fix
            elif (
                auto_mark_low_quality_lines
                and status == SubtitleReviewStatus.needs_fix
                and line.edited_text
                and not quality.needs_review
            ):
                status = SubtitleReviewStatus.reviewed
            updated_lines.append(
                line.model_copy(
                    update={
                        "warnings": _dedupe(warnings),
                        "status": status,
                        "quality_score": quality.score,
                        "quality_needs_review": quality.needs_review,
                        "quality_severity": quality.severity.value,
                        "quality_issues": quality.issues,
                    }
                )
            )
        updated_document = document.model_copy(
            update={
                "lines": updated_lines,
                "quality_average_score": saved_report.average_score,
                "quality_needs_review_count": saved_report.needs_review_count,
                "quality_critical_count": saved_report.critical_count,
                "quality_warning_count": saved_report.warning_count,
                "warning_count": sum(len(line.warnings) for line in updated_lines),
                "updated_at": saved_report.created_at,
            }
        )
        self.review_repository.update_document(updated_document)
        write_json(report_path, saved_report.model_dump(mode="json"))
        return saved_report


def _load_debug(translated_srt_path: str, kind: str) -> dict | None:
    directory = Path(translated_srt_path).parent
    patterns = ["*_ocr_debug.json"] if kind == "ocr" else ["*_asr_debug.json", "*asr*.json"]
    for pattern in patterns:
        for path in sorted(directory.glob(pattern)):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except (OSError, json.JSONDecodeError):
                continue
    return None


def _duration_ms(video_path: str) -> int | None:
    try:
        from app.adapters.ffmpeg_adapter import probe_video

        return int(probe_video(video_path).duration * 1000)
    except Exception:
        return None


def _shorten_rule_based(text: str) -> str:
    cleaned = re.sub(r"\x60\x60\x60|[{}\[\]]|\"translation\"\s*:|SRT\s*:", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,:;")
    if len(cleaned) <= 56:
        return cleaned
    parts = re.split(r"(?<=[.!?])\s+|[,;]\s*", cleaned)
    candidate = next((part.strip() for part in parts if 3 <= len(part.strip()) <= 56), "")
    return candidate or cleaned[:53].rstrip() + "..."


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
