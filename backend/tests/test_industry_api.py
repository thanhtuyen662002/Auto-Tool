from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_industry_api_lists_detail_and_applies_preset(tmp_path) -> None:
    database.DB_PATH = tmp_path / "industry-api.db"

    with TestClient(create_app()) as client:
        listed = client.get("/api/industry-presets")
        assert listed.status_code == 200
        presets = listed.json()["presets"]
        assert len(presets) >= 8
        assert any(item["id"] == "tech_electronics" for item in presets)

        detail = client.get("/api/industry-presets/tech_electronics")
        assert detail.status_code == 200
        assert detail.json()["visual_style_preset_id"] == "tech_dark_neon"

        created = client.post("/api/projects", json=_project_config(tmp_path))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        applied = client.put(
            f"/api/projects/{project_id}/industry-preset",
            json={
                "preset_id": "tech_electronics",
                "apply_visual_style": True,
                "apply_timeline": True,
                "apply_script_variation": True,
                "apply_tts_voice": True,
                "apply_edit_strength": True,
            },
        )
        assert applied.status_code == 200
        payload = applied.json()
        assert payload["preset_id"] == "tech_electronics"
        config = payload["updated_config"]
        assert config["industry"]["preset_id"] == "tech_electronics"
        assert config["timeline"]["template_id"] == "product_showcase_clean"
        assert config["visual_style"]["preset_id"] == "tech_dark_neon"
        assert config["tts"]["voice"] == "vi-VN-NamMinhNeural"
        assert config["script_variation"]["preferred_variant_ids"][0] == "benefit_first"


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    return {
        "project_name": "industry-api-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Máy chiếu test",
            "brand": "KAW",
            "description": "Mô tả test.",
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

