from pathlib import Path

from app import database
from app.modules.subtitle_review import SubtitleReviewService
from app.modules.subtitle_rewrite.subtitle_rewrite_repository import SubtitleRewriteRepository


def test_review_document_can_auto_generate_fallback_rewrite_log(tmp_path: Path):
    database.DB_PATH = tmp_path / "rewrite-integration.db"
    translated = tmp_path / "translated.srt"
    translated.write_text(
        "1\n00:00:00,000 --> 00:00:04,000\n" + "Mot cau phu de rat dai " * 6 + "\n",
        encoding="utf-8",
    )

    document = SubtitleReviewService().create_document_from_srt(
        video_id="rewrite-auto-video",
        video_path=str(tmp_path / "video.mp4"),
        translated_srt_path=str(translated),
        enable_subtitle_rewrite_suggestions=True,
        auto_generate_rewrite_for_flagged_lines=True,
        auto_apply_safe_rewrites=False,
    )
    suggestions = SubtitleRewriteRepository().list_for_line(document.id, 1)

    assert suggestions
    assert (tmp_path / "subtitle_rewrite_log.json").exists()
    assert document.lines[0].quality_needs_review is True
