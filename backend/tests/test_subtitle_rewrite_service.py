import json
from pathlib import Path

from app import database
from app.modules.subtitle_review import SubtitleReviewService
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import (
    ApplySubtitleRewriteRequest,
    BulkRewriteFlaggedLinesRequest,
    GenerateSubtitleRewriteRequest,
)
from app.modules.subtitle_rewrite.subtitle_rewrite_service import SubtitleRewriteService


LONG_TEXT = (
    "Cac ban co the thay san pham nay that su rat tien loi khi su dung "
    "va co the giup ban tiet kiem thoi gian moi ngay."
)


class FakeGeminiAdapter:
    def generate_json(self, _prompt: str) -> dict:
        return {
            "suggestions": [
                {"text": "Mon nay dung tien va tiet kiem thoi gian.", "reason": "Ngan gon hon."},
                {"text": "Dung tien, lai tiet kiem thoi gian.", "reason": "De doc hon."},
            ]
        }


def _document(tmp_path: Path, text: str = LONG_TEXT):
    database.DB_PATH = tmp_path / "rewrite-service.db"
    translated = tmp_path / "translated.srt"
    translated.write_text(f"1\n00:00:00,000 --> 00:00:04,000\n{text}\n", encoding="utf-8")
    return SubtitleReviewService().create_document_from_srt(
        video_id="rewrite-video",
        video_path=str(tmp_path / "video.mp4"),
        translated_srt_path=str(translated),
    )


def test_generate_and_apply_rewrite_refreshes_quality_and_history(tmp_path: Path):
    document = _document(tmp_path)
    service = SubtitleRewriteService(gemini_adapter=FakeGeminiAdapter())

    suggestions = service.generate_suggestions_for_line(
        document.id,
        1,
        GenerateSubtitleRewriteRequest(use_ai=True),
    )
    updated = service.apply_suggestion(
        document.id,
        1,
        ApplySubtitleRewriteRequest(suggestion_id=suggestions[0].id),
    )

    assert len(suggestions) == 2
    assert suggestions[0].char_count_after < suggestions[0].char_count_before
    assert suggestions[0].quality_score_after > suggestions[0].quality_score_before
    assert updated.edited_text == suggestions[0].suggested_text
    assert updated.quality_score == suggestions[0].quality_score_after
    assert updated.rewrite_history[-1]["suggestion_id"] == suggestions[0].id
    log = json.loads((tmp_path / "subtitle_rewrite_log.json").read_text(encoding="utf-8"))
    assert log["suggestions_created"] == 2
    assert log["suggestions_applied"] == 1
    assert log["applied_items"][0]["suggestion_id"] == suggestions[0].id


def test_gemini_failure_uses_rule_based_fallback_without_crash(tmp_path: Path):
    document = _document(tmp_path)
    service = SubtitleRewriteService()

    suggestions = service.generate_suggestions_for_line(
        document.id,
        1,
        GenerateSubtitleRewriteRequest(use_ai=False),
    )

    assert len(suggestions) == 1
    assert suggestions[0].suggested_text
    assert "AI rewrite unavailable, used rule-based fallback." in suggestions[0].safety_warnings


def test_bulk_rewrite_filters_flagged_lines_and_auto_applies_only_safe_suggestion(tmp_path: Path):
    document = _document(tmp_path)
    service = SubtitleRewriteService(gemini_adapter=FakeGeminiAdapter())

    response = service.generate_suggestions_for_flagged_lines(
        document.id,
        BulkRewriteFlaggedLinesRequest(
            only_issue_types=["too_long"],
            auto_apply_safe_suggestions=True,
        ),
    )
    refreshed = SubtitleReviewService().get_document(document.id)

    assert response.processed_lines == 1
    assert response.suggestions_created == 2
    assert response.auto_applied == 1
    assert refreshed.lines[0].edited_text
    assert refreshed.lines[0].rewrite_history[-1]["auto_applied"] is True
