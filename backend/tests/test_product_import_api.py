from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_product_info_import_api_returns_normalized_schema(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-import-api.db"

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/product-info/import",
            json={
                "input_type": "text",
                "raw_text": "Máy Chiếu 4K Android KAW XMAX10\nThương hiệu: KAW\nHỗ trợ 4K\nAndroid 9.0",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["product"]["name"] == "Máy Chiếu 4K Android KAW XMAX10"
    assert payload["product"]["brand"] == "KAW"
    assert payload["product"]["industry_preset_id"] == "tech_electronics"
    assert isinstance(payload["product"]["confidence_score"], float)


def test_apply_imported_product_to_project_updates_config(tmp_path: Path) -> None:
    database.DB_PATH = tmp_path / "product-apply-api.db"

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=_project_config(tmp_path))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        imported = client.post(
            "/api/product-info/import",
            json={
                "input_type": "json",
                "raw_text": """
{
  "product_name": "Máy chiếu KAW XMAX10",
  "brand_name": "KAW",
  "description": "Máy chiếu nhỏ gọn hỗ trợ 4K.",
  "features": ["Hỗ trợ 4K", "Android 9.0", "Thiết kế nhỏ gọn"],
  "specifications": {"Độ sáng": "10.000 Lumens"}
}
""",
            },
        )
        assert imported.status_code == 200
        product = imported.json()["product"]

        applied = client.put(f"/api/projects/{project_id}/product-info", json={"product": product})

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["success"] is True
    assert payload["updated_config"]["product"]["name"] == "Máy chiếu KAW XMAX10"
    assert payload["updated_config"]["product"]["specs"][0]["name"] == "Độ sáng"
    assert payload["updated_config"]["industry"]["preset_id"] == "tech_electronics"


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    return {
        "project_name": "product-import-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Sản phẩm cũ",
            "brand": "OLD",
            "description": "Mô tả cũ.",
            "features": ["Tính năng cũ"],
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
