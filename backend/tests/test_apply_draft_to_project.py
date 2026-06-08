from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_apply_draft_to_existing_project_updates_product_info(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "apply-draft.db"

    with TestClient(create_app()) as client:
        created_project = client.post("/api/projects", json=_project_config(tmp_path))
        assert created_project.status_code == 200
        project_id = created_project.json()["project_id"]

        created_draft = client.post("/api/product-info/import", json={**_draft_payload(), "save_to_inbox": True})
        assert created_draft.status_code == 200
        draft_id = created_draft.json()["draft"]["id"]

        applied = client.post(f"/api/product-drafts/{draft_id}/apply-to-project/{project_id}")
        project = client.get(f"/api/projects/{project_id}")
        draft = client.get(f"/api/product-drafts/{draft_id}")

    assert applied.status_code == 200
    assert applied.json()["success"] is True
    assert applied.json()["project_product"]["name"] == "May chieu KAW XMAX10"
    assert project.json()["config"]["product"]["name"] == "May chieu KAW XMAX10"
    assert project.json()["config"]["industry"]["preset_id"] == "tech_electronics"
    assert draft.json()["status"] == "applied"


def test_create_project_from_draft_creates_project(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "create-project-from-draft.db"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()

    with TestClient(create_app()) as client:
        created_draft = client.post("/api/product-info/import", json={**_draft_payload(), "save_to_inbox": True})
        draft_id = created_draft.json()["draft"]["id"]

        created_project = client.post(
            f"/api/product-drafts/{draft_id}/create-project",
            json={
                "project_name": "kaw-xmax10",
                "source_folder": str(source_dir),
                "output_folder": str(output_dir),
                "render": {"output_count": 3, "duration": 12},
            },
        )
        project_id = created_project.json()["project_id"]
        project = client.get(f"/api/projects/{project_id}")

    assert created_project.status_code == 200
    assert created_project.json()["success"] is True
    assert project.status_code == 200
    assert project.json()["config"]["product"]["name"] == "May chieu KAW XMAX10"
    assert project.json()["config"]["render"]["output_count"] == 3
    assert project.json()["config"]["industry"]["preset_id"] == "tech_electronics"
    assert project.json()["config"]["music"]["enabled"] is True
    assert project.json()["config"]["music"]["source_folder"] == "examples/music"


def _draft_payload() -> dict:
    return {
        "input_type": "shopee_extension",
        "source_name": "shopee",
        "source_url": "https://shopee.vn/May-chieu-KAW-XMAX10-i.1.2",
        "raw_text": "Ten san pham: May chieu KAW XMAX10",
        "structured_data": {
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0", "Do sang cao"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem ngay",
        },
    }


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "existing-source"
    output_dir = tmp_path / "existing-output"
    source_dir.mkdir()
    output_dir.mkdir()
    return {
        "project_name": "existing",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Old product",
            "brand": "OLD",
            "description": "Old description.",
            "features": ["Old feature"],
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
        "visual_style": {"preset_id": "clean_review_light", "custom_overrides": None},
        "industry": {"preset_id": "general_product"},
    }
