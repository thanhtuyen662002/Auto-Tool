from __future__ import annotations

import re

from app.modules.subtitle_review.subtitle_review_schema import (
    SubtitleLine,
    SubtitleReviewDocument,
    SubtitleReviewStatus,
)


class SubtitleValidationService:
    def validate_line(self, line: SubtitleLine, video_duration_ms: int | None = None) -> SubtitleLine:
        warnings = list(line.warnings)
        text = (line.edited_text or line.translated_text or "").strip()
        duration_ms = max(0, line.end_ms - line.start_ms)

        if line.start_ms < 0:
            warnings.append("start_ms nhỏ hơn 0.")
        if line.end_ms <= line.start_ms:
            warnings.append("end_ms phải lớn hơn start_ms.")
        if video_duration_ms is not None and line.end_ms > video_duration_ms:
            warnings.append("Subtitle vượt quá duration video.")
        if not text:
            warnings.append("Subtitle text đang rỗng.")
        if len(text) > 120:
            warnings.append("Subtitle text quá dài.")
        display_lines = [part for part in text.splitlines() if part.strip()] or [text]
        if len(display_lines) > 2:
            warnings.append("Subtitle nên tối đa 2 dòng.")
        if any(len(part.strip()) > 28 for part in display_lines):
            warnings.append("Mỗi dòng subtitle nên khoảng 22-28 ký tự.")
        if duration_ms < 1400 and len(text) > 48:
            warnings.append("Duration ngắn nhưng subtitle dài, người xem có thể đọc không kịp.")
        if re.search(r"[*_`#\[\]<>]", text):
            warnings.append("Subtitle có ký tự markdown hoặc ký tự lạ.")

        status = line.status
        if any("rỗng" in warning or "end_ms" in warning or "start_ms" in warning for warning in warnings):
            status = SubtitleReviewStatus.needs_fix
        return line.model_copy(update={"warnings": _dedupe(warnings), "status": status})

    def validate_document(
        self,
        document: SubtitleReviewDocument,
        video_duration_ms: int | None = None,
    ) -> SubtitleReviewDocument:
        lines = [self.validate_line(line, video_duration_ms=video_duration_ms) for line in document.lines]
        return document.model_copy(update=_document_counts(lines, status=document.status))


def _document_counts(lines: list[SubtitleLine], status: SubtitleReviewStatus) -> dict:
    return {
        "lines": lines,
        "line_count": len(lines),
        "reviewed_count": sum(1 for line in lines if line.status in {SubtitleReviewStatus.reviewed, SubtitleReviewStatus.approved}),
        "edited_count": sum(1 for line in lines if bool((line.edited_text or "").strip())),
        "warning_count": sum(len(line.warnings) for line in lines),
        "status": status,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned
