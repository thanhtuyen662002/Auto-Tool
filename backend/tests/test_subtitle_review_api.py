from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.subtitle_review import SubtitleReviewService


def test_subtitle_review_api_lifecycle_and_render_queue(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-subtitle-review-api.db"
    monkeypatch.setattr("app.modules.subtitle_review.subtitle_review_service._duration_ms", lambda _path: None)
    monkeypatch.setattr("app.api.run_subtitle_review_render_job", lambda *args, **kwargs: None)

    video = tmp_path / "clip.mp4"
    translated = tmp_path / "clip.vi_fixed.srt"
    video.write_bytes(b"fake video")
    translated.write_text("1\n00:00:00,000 --> 00:00:01,000\nXin chao\n", encoding="utf-8")
    document = SubtitleReviewService().create_document_from_srt(
        video_id="video-api",
        video_path=str(video),
        translated_srt_path=str(translated),
        project_id="project-api",
        job_id="job-api",
    )

    with TestClient(create_app()) as client:
        listed = client.get("/api/subtitle-review/documents", params={"job_id": "job-api"})
        assert listed.status_code == 200
        assert listed.json()["items"][0]["id"] == document.id

        detail = client.get(f"/api/subtitle-review/documents/{document.id}")
        assert detail.status_code == 200
        assert detail.json()["line_count"] == 1

        updated_line = client.put(
            f"/api/subtitle-review/documents/{document.id}/lines/1",
            json={"edited_text": "Xin chao ban", "status": "reviewed"},
        )
        assert updated_line.status_code == 200
        assert updated_line.json()["edited_text"] == "Xin chao ban"

        current = client.get(f"/api/subtitle-review/documents/{document.id}").json()
        saved = client.put(
            f"/api/subtitle-review/documents/{document.id}",
            json={"lines": current["lines"], "mark_as_reviewed": True},
        )
        assert saved.status_code == 200
        assert saved.json()["reviewed_count"] == 1

        approved = client.post(
            f"/api/subtitle-review/documents/{document.id}/approve",
            json={"generate_ass": False},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        queued = client.post(
            f"/api/subtitle-review/documents/{document.id}/render",
            json={"output_folder": str(tmp_path / "renders")},
        )
        assert queued.status_code == 200
        assert queued.json()["status"] == "queued"
