from pathlib import Path

from app import database
from app.modules.subtitle_quality.subtitle_quality_service import SubtitleQualityService
from app.modules.subtitle_review import SubtitleReviewService, UpdateSubtitleLineRequest


def _write_srt(path: Path, text: str) -> None:
    path.write_text(f"1\n00:00:00,000 --> 00:00:01,000\n{text}\n", encoding="utf-8")


def test_quality_report_created_and_refreshes_after_edit(tmp_path: Path):
    database.DB_PATH = tmp_path / "quality-service.db"
    source = tmp_path / "source.srt"
    translated = tmp_path / "translated.srt"
    _write_srt(source, "这是一个很长的中文原文内容")
    _write_srt(translated, "还有中文内容")

    review_service = SubtitleReviewService()
    document = review_service.create_document_from_srt(
        video_id="video-quality",
        video_path=str(tmp_path / "video.mp4"),
        source_srt_path=str(source),
        translated_srt_path=str(translated),
        source_type="sidecar_srt",
    )
    first_report = SubtitleQualityService().get_quality_report(document.id)

    assert first_report.critical_count == 1
    assert document.quality_critical_count == 1
    assert document.lines[0].status.value == "needs_fix"
    assert Path(first_report.report_file).exists()

    review_service.update_line(
        document.id,
        1,
        UpdateSubtitleLineRequest(edited_text="Câu ngắn, tự nhiên.", status=None),
    )
    refreshed = SubtitleQualityService().get_quality_report(document.id)
    updated_document = review_service.get_document(document.id)

    assert refreshed.average_score > first_report.average_score
    assert refreshed.critical_count == 0
    assert updated_document.lines[0].status.value == "reviewed"
