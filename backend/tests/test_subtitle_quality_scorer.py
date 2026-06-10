from app.modules.subtitle_quality.subtitle_quality_scorer import SubtitleQualityScorer
from app.modules.subtitle_review.subtitle_review_schema import (
    SubtitleLine,
    SubtitleReviewDocument,
    SubtitleReviewStatus,
)


def _line(index: int, text: str, start_ms: int, end_ms: int) -> SubtitleLine:
    return SubtitleLine.model_construct(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        source_text="中文原文",
        translated_text=text,
        edited_text=None,
        status=SubtitleReviewStatus.pending,
        warnings=[],
        user_note=None,
        quality_score=None,
        quality_needs_review=False,
        quality_severity=None,
        quality_issues=[],
    )


def test_score_line_and_document_average():
    scorer = SubtitleQualityScorer()
    good = _line(1, "Câu ngắn dễ đọc.", 0, 2000)
    bad = _line(2, "还有中文内容", 2100, 2400)
    document = SubtitleReviewDocument(
        id="doc-score",
        video_id="video-1",
        video_path="video.mp4",
        translated_srt_path="translated.srt",
        lines=[good, bad],
        line_count=2,
        created_at="2026-06-10T00:00:00",
        updated_at="2026-06-10T00:00:00",
    )

    report = scorer.score_document(document, video_duration_ms=3000)

    assert report.total_lines == 2
    assert report.lines[0].score == 1.0
    assert report.lines[1].severity.value == "critical"
    assert report.average_score == round(sum(line.score for line in report.lines) / 2, 4)
    assert report.needs_review_count == 1


def test_ocr_confidence_and_overlap_are_scored():
    scorer = SubtitleQualityScorer()
    first = _line(1, "Câu một", 0, 1200)
    second = _line(2, "Câu hai", 1000, 2200)

    score = scorer.score_line(
        first,
        next_line=second,
        source_type="ocr_hardsub",
        ocr_confidence=0.5,
    )

    types = {issue.issue_type.value for issue in score.issues}
    assert {"ocr_low_confidence", "timestamp_overlap"}.issubset(types)
