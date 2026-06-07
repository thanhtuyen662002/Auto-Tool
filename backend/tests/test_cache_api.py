from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_project_cache_summary_and_clear_api(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    config = _config(tmp_path)

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=config)
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        cache_file = Path(config["output_folder"]) / config["project_name"] / ".cache" / "media_metadata" / "one.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_text(json.dumps({"path": "one.mp4"}), encoding="utf-8")

        summary = client.get(f"/api/projects/{project_id}/cache/summary")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["enabled"] is True
        assert payload["items"]["media_metadata"] == 1

        cleared = client.post(f"/api/projects/{project_id}/cache/clear")
        assert cleared.status_code == 200
        assert cleared.json()["success"] is True
        assert not list(cache_file.parent.glob("*.json"))


def _config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    return {
        "project_name": "cache-api-test",
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
    }
