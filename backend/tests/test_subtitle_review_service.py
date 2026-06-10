from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.subtitle_review import (
    ApproveSubtitleDocumentRequest,
    SaveSubtitleReviewRequest,
    SubtitleReviewService,
    SubtitleReviewStatus,
    UpdateSubtitleLineRequest,
)


def test_subtitle_review_service_create_edit_and_approve_exports_corrected_srt(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-subtitle-review.db"
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    video = tmp_path / "clip.mp4"
    source = tmp_path / "clip.source.srt"
    translated = tmp_path / "clip.vi_fixed.srt"
    video.write_bytes(b"fake video")
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\nNi hao\n", encoding="utf-8")
    translated.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")

    service = SubtitleReviewService()
    document = service.create_document_from_srt(
        video_id="video-1",
        video_path=str(video),
        source_srt_path=str(source),
        translated_srt_path=str(translated),
        project_id="project-1",
        job_id="job-1",
    )

    assert document.status == SubtitleReviewStatus.pending
    assert document.line_count == 1
    assert document.lines[0].source_text == "Ni hao"

    service.update_line(
        document.id,
        1,
        UpdateSubtitleLineRequest(edited_text="Xin chao ban", status=SubtitleReviewStatus.reviewed),
    )
    saved = service.save_document(
        document.id,
        SaveSubtitleReviewRequest(lines=service.get_document(document.id).lines, mark_as_reviewed=True),
    )
    assert saved.reviewed_count == 1
    assert saved.edited_count == 1

    approved = service.approve_document(document.id, ApproveSubtitleDocumentRequest(generate_ass=False))

    assert approved.status == SubtitleReviewStatus.approved
    assert approved.corrected_srt_path
    corrected = Path(approved.corrected_srt_path).read_text(encoding="utf-8")
    assert "Xin chao ban" in corrected
