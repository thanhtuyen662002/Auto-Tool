from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.subtitle_review import SubtitleReviewService


def test_subtitle_quality_api_report_flagged_refresh_and_suggestion(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "quality-api.db"
    translated = tmp_path / "translated.srt"
    translated.write_text(
        "1\n00:00:00,000 --> 00:00:00,400\n还有中文内容\n",
        encoding="utf-8",
    )
    document = SubtitleReviewService().create_document_from_srt(
        video_id="video-api",
        video_path=str(tmp_path / "video.mp4"),
        translated_srt_path=str(translated),
    )
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    with TestClient(create_app()) as client:
        report = client.get(f"/api/subtitle-review/documents/{document.id}/quality")
        flagged = client.get(f"/api/subtitle-review/documents/{document.id}/quality/flagged-lines")
        refresh = client.post(f"/api/subtitle-review/documents/{document.id}/quality/refresh")
        suggestion = client.post(
            f"/api/subtitle-review/documents/{document.id}/lines/1/suggest-rewrite",
            json={"style": "short_natural_vietnamese"},
        )

    assert report.status_code == 200
    assert report.json()["critical_count"] == 1
    assert flagged.status_code == 200
    assert flagged.json()["items"][0]["line_index"] == 1
    assert refresh.status_code == 200
    assert suggestion.status_code == 200
    assert suggestion.json()["suggestion"]
