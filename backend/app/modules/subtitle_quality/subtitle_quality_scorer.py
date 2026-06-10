from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.modules.subtitle_quality.subtitle_quality_rules import evaluate_line_quality
from app.modules.subtitle_quality.subtitle_quality_schema import (
    SubtitleDocumentQualityReport,
    SubtitleLineQualityScore,
    SubtitleQualityIssue,
    SubtitleQualitySeverity,
)
from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine, SubtitleReviewDocument


class SubtitleQualityScorer:
    def score_line(
        self,
        line: SubtitleLine,
        previous_line: SubtitleLine | None = None,
        next_line: SubtitleLine | None = None,
        source_type: str | None = None,
        ocr_confidence: float | None = None,
        asr_confidence: float | None = None,
        video_duration_ms: int | None = None,
    ) -> SubtitleLineQualityScore:
        text = (line.edited_text if line.edited_text is not None else line.translated_text) or ""
        duration_ms = max(0, int(line.end_ms) - int(line.start_ms))
        display_lines = [part for part in text.splitlines() if part.strip()] or ([text] if text else [])
        char_count = len(text.replace("\n", "").strip())
        chars_per_second = (char_count / (duration_ms / 1000)) if duration_ms > 0 else float(char_count)
        issues = evaluate_line_quality(
            source_text=line.source_text,
            text=text,
            duration_ms=duration_ms,
            line_count=len(display_lines),
            chars_per_second=chars_per_second,
            next_start_ms=next_line.start_ms if next_line else None,
            current_end_ms=line.end_ms,
            video_duration_ms=video_duration_ms,
            ocr_confidence=ocr_confidence if source_type == "ocr_hardsub" else None,
            asr_confidence=asr_confidence if source_type == "asr" else None,
            repeated_three_times=_same_translation(previous_line, line) and _same_translation(line, next_line),
        )
        score = _score_from_issues(issues)
        severity = _severity_from_issues(issues)
        return SubtitleLineQualityScore(
            line_index=line.index,
            score=score,
            severity=severity,
            needs_review=score < 0.75 or severity in {SubtitleQualitySeverity.warning, SubtitleQualitySeverity.critical},
            source_text=line.source_text,
            translated_text=line.translated_text,
            edited_text=line.edited_text,
            duration_ms=duration_ms,
            char_count=char_count,
            line_count=len(display_lines),
            chars_per_second=round(chars_per_second, 3),
            ocr_confidence=ocr_confidence if source_type == "ocr_hardsub" else None,
            asr_confidence=asr_confidence if source_type == "asr" else None,
            issues=issues,
        )

    def score_document(
        self,
        document: SubtitleReviewDocument,
        source_type: str | None = None,
        ocr_debug: dict | None = None,
        asr_debug: dict | None = None,
        video_duration_ms: int | None = None,
    ) -> SubtitleDocumentQualityReport:
        ocr_conf_by_index = _confidence_by_line_index(ocr_debug)
        asr_conf_by_index = _confidence_by_line_index(asr_debug)
        lines: list[SubtitleLineQualityScore] = []
        for index, line in enumerate(document.lines):
            lines.append(
                self.score_line(
                    line,
                    previous_line=document.lines[index - 1] if index > 0 else None,
                    next_line=document.lines[index + 1] if index + 1 < len(document.lines) else None,
                    source_type=source_type or document.source_type,
                    ocr_confidence=ocr_conf_by_index.get(line.index) or _average_confidence(ocr_debug),
                    asr_confidence=asr_conf_by_index.get(line.index) or _average_confidence(asr_debug),
                    video_duration_ms=video_duration_ms,
                )
            )
        total = len(lines)
        average_score = sum(line.score for line in lines) / total if total else 1.0
        issues = [issue for line in lines for issue in line.issues]
        breakdown = Counter(issue.issue_type.value for issue in issues)
        return SubtitleDocumentQualityReport(
            document_id=document.id,
            video_id=document.video_id,
            project_id=document.project_id,
            average_score=round(average_score, 4),
            total_lines=total,
            needs_review_count=sum(1 for line in lines if line.needs_review),
            critical_count=sum(1 for line in lines if line.severity == SubtitleQualitySeverity.critical),
            warning_count=sum(1 for line in lines if line.severity == SubtitleQualitySeverity.warning),
            lines=lines,
            summary_warnings=_summary_warnings(lines),
            issues_breakdown=dict(breakdown),
            created_at=datetime.now().replace(microsecond=0).isoformat(),
        )


def _score_from_issues(issues: list[SubtitleQualityIssue]) -> float:
    score = 1.0
    for issue in issues:
        if issue.severity == SubtitleQualitySeverity.critical:
            score -= 0.35
        elif issue.severity == SubtitleQualitySeverity.warning:
            score -= 0.15
        else:
            score -= 0.05
    return round(max(0.0, min(1.0, score)), 4)


def _severity_from_issues(issues: list[SubtitleQualityIssue]) -> SubtitleQualitySeverity:
    severities = {issue.severity for issue in issues}
    if SubtitleQualitySeverity.critical in severities:
        return SubtitleQualitySeverity.critical
    if SubtitleQualitySeverity.warning in severities:
        return SubtitleQualitySeverity.warning
    return SubtitleQualitySeverity.info


def _same_translation(left: SubtitleLine | None, right: SubtitleLine | None) -> bool:
    if not left or not right:
        return False
    left_text = ((left.edited_text if left.edited_text is not None else left.translated_text) or "").strip().lower()
    right_text = ((right.edited_text if right.edited_text is not None else right.translated_text) or "").strip().lower()
    return bool(left_text and left_text == right_text)


def _confidence_by_line_index(debug: dict | None) -> dict[int, float]:
    if not debug:
        return {}
    mapping: dict[int, float] = {}
    for fallback_index, item in enumerate(debug.get("lines") or [], start=1):
        if not isinstance(item, dict):
            continue
        index = int(item.get("index") or fallback_index)
        confidence = item.get("confidence")
        if confidence is not None:
            mapping[index] = float(confidence)
    return mapping


def _average_confidence(debug: dict | None) -> float | None:
    if not debug:
        return None
    value = debug.get("average_confidence")
    return float(value) if value is not None else None


def _summary_warnings(lines: list[SubtitleLineQualityScore]) -> list[str]:
    warnings: list[str] = []
    critical = sum(1 for line in lines if line.severity == SubtitleQualitySeverity.critical)
    flagged = sum(1 for line in lines if line.needs_review)
    if critical:
        warnings.append(f"Có {critical} dòng phụ đề lỗi nghiêm trọng. Nên sửa trước khi approve.")
    if flagged:
        warnings.append(f"Có {flagged} dòng cần kiểm tra kỹ.")
    return warnings
