from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.subtitle_review import SubtitleReviewService


def test_subtitle_rewrite_generate_apply_and_bulk_api(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "rewrite-api.db"
    translated = tmp_path / "translated.srt"
    translated.write_text(
        "1\n00:00:00,000 --> 00:00:04,000\n"
        "Cac ban co the thay san pham nay that su rat tien loi khi su dung va co the giup ban tiet kiem thoi gian moi ngay.\n",
        encoding="utf-8",
    )
    document = SubtitleReviewService().create_document_from_srt(
        video_id="rewrite-api-video",
        video_path=str(tmp_path / "video.mp4"),
        translated_srt_path=str(translated),
    )
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    with TestClient(create_app()) as client:
        generated = client.post(
            f"/api/subtitle-review/documents/{document.id}/lines/1/rewrite-suggestions",
            json={
                "style": "short_natural",
                "suggestion_count": 3,
                "max_chars": 56,
                "preserve_keywords": [],
                "use_ai": False,
            },
        )
        suggestion_id = generated.json()["items"][0]["id"]
        applied = client.post(
            f"/api/subtitle-review/documents/{document.id}/lines/1/apply-rewrite",
            json={"suggestion_id": suggestion_id, "refresh_quality_score": True},
        )
        bulk = client.post(
            f"/api/subtitle-review/documents/{document.id}/rewrite-flagged-lines",
            json={
                "style": "short_natural",
                "max_lines": 20,
                "only_issue_types": ["too_long"],
                "auto_apply_safe_suggestions": False,
            },
        )

    assert generated.status_code == 200
    assert generated.json()["items"]
    assert applied.status_code == 200
    assert applied.json()["line"]["edited_text"]
    assert applied.json()["line"]["rewrite_history"]
    assert bulk.status_code == 200
    assert bulk.json()["success"] is True
