from __future__ import annotations

from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine, SubtitleReviewDocument, SubtitleReviewStatus
from app.modules.subtitle_review.subtitle_validation_service import SubtitleValidationService


def test_validation_marks_bad_timing_as_needs_fix():
    service = SubtitleValidationService()
    line = SubtitleLine(index=1, start_ms=1500, end_ms=1000, translated_text="Xin chao")

    validated = service.validate_line(line)

    assert validated.status == SubtitleReviewStatus.needs_fix
    assert validated.warnings


def test_validation_counts_reviewed_edited_and_warnings():
    service = SubtitleValidationService()
    document = SubtitleReviewDocument(
        id="doc-1",
        video_id="video-1",
        video_path="video.mp4",
        translated_srt_path="translated.srt",
        status=SubtitleReviewStatus.pending,
        lines=[
            SubtitleLine(index=1, start_ms=0, end_ms=1000, translated_text="Xin chao", status=SubtitleReviewStatus.reviewed),
            SubtitleLine(index=2, start_ms=1000, end_ms=900, translated_text="Auto", edited_text="Manual"),
        ],
        line_count=2,
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )

    validated = service.validate_document(document)

    assert validated.line_count == 2
    assert validated.reviewed_count == 1
    assert validated.edited_count == 1
    assert validated.warning_count > 0
