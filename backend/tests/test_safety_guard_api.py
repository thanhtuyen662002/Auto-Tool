from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_safety_check_endpoint_returns_warnings(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "safety-api.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=_project_config(tmp_path, feature="100% hiệu quả"))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        response = client.post(f"/api/projects/{project_id}/safety-check")

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is True
    assert payload["warnings_count"] >= 1


def test_render_is_blocked_when_product_name_is_blank(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "safety-render-block.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=_project_config(tmp_path, name="   "))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        response = client.post(f"/api/projects/{project_id}/render", json={"preview_only": True})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "Product info safety check failed"


def test_render_still_queues_when_product_has_warning_only(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "safety-render-warning.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=_project_config(tmp_path, feature="100% hiệu quả"))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        response = client.post(f"/api/projects/{project_id}/render", json={"preview_only": True})

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def _project_config(tmp_path: Path, name: str = "Máy chiếu KAW", feature: str = "Hỗ trợ 4K") -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    return {
        "project_name": "safety-api-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": name,
            "brand": "KAW",
            "description": "Máy chiếu nhỏ gọn hỗ trợ 4K.",
            "features": [feature],
            "specs": [],
            "cta": "Xem ngay",
            "validation_warnings": [],
            "hashtag_suggestions": [],
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
            "zoom_motion": 0,
            "overlay_height": 33,
            "subtitle_size": 84,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
        "music": {
            "enabled": False,
            "source_folder": None,
            "source_file": None,
            "volume": 0.12,
            "fade_in": 0.5,
            "fade_out": 0.8,
            "duck_under_voice": False,
        },
        "visual_style": {
            "preset_id": "clean_review_light",
            "custom_overrides": None,
        },
        "industry": {
            "preset_id": "general_product",
        },
    }
