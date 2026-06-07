from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_crop_safety_api_returns_latest_report_after_preview_job(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "crop-safety-api.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=_project_config(tmp_path))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        missing = client.post(f"/api/projects/{project_id}/crop-safety/analyze")
        assert missing.status_code == 200
        assert missing.json()["success"] is False

        report_dir = tmp_path / "outputs" / "preview"
        report_dir.mkdir(parents=True)
        report_path = report_dir / "crop_safety_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "project_id": project_id,
                    "total_clips_analyzed": 3,
                    "average_crop_safety_score": 0.81,
                    "fallback_to_blur_background": 1,
                    "center_crop_used": 2,
                    "warnings_summary": {"important_content_near_edge": 1},
                    "clips": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        database.create_job("crop-job-1", project_id, preview_only=True, total_outputs=1)
        database.update_job("crop-job-1", status="completed", output_folder=str(report_dir))

        response = client.post(f"/api/projects/{project_id}/crop-safety/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["total_clips_analyzed"] == 3
    assert payload["average_crop_safety_score"] == 0.81
    assert payload["fallback_to_blur_background"] == 1
    assert payload["warnings_summary"] == {"important_content_near_edge": 1}
    assert payload["report_path"] == str(report_path)


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    return {
        "project_name": "crop-safety-api-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Máy chiếu KAW",
            "brand": "KAW",
            "description": "Máy chiếu nhỏ gọn.",
            "features": ["Hỗ trợ 4K"],
            "cta": "Xem ngay",
        },
        "render": {
            "output_count": 1,
            "duration": 8,
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "fps": 30,
        },
        "effects": {
            "cut_intensity": 70,
            "speed_variation": 30,
            "grain": 0,
            "zoom_motion": 25,
            "overlay_height": 33,
            "subtitle_size": 84,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
    }
