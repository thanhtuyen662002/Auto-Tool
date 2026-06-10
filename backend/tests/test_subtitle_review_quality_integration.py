from pathlib import Path

from app import database
from app.modules.subtitle_review import ApproveSubtitleDocumentRequest, SubtitleReviewService


def test_review_document_auto_quality_and_approve_guard(tmp_path: Path):
    database.DB_PATH = tmp_path / "quality-integration.db"
    translated = tmp_path / "translated.srt"
    translated.write_text(
        "1\n00:00:00,000 --> 00:00:00,300\n还有中文内容\n",
        encoding="utf-8",
    )
    service = SubtitleReviewService()
    document = service.create_document_from_srt(
        video_id="video-guard",
        video_path=str(tmp_path / "video.mp4"),
        translated_srt_path=str(translated),
    )

    assert document.quality_average_score is not None
    assert document.quality_critical_count == 1
    assert document.lines[0].quality_needs_review is True

    approved = service.approve_document(
        document.id,
        ApproveSubtitleDocumentRequest(generate_ass=False),
    )

    assert approved.status.value == "approved"
    assert approved.approval_quality_warning
    assert approved.approval_quality_guard["critical_count"] == 1
