from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app


def test_v1_health_and_presets_api_contract() -> None:
    client = TestClient(create_app())

    health = client.get("/api/health")
    presets = client.get("/api/douyin-reup/presets")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": "1.0.0-rc1"}
    assert presets.status_code == 200
    preset_ids = {preset["id"] for preset in presets.json()["presets"]}
    assert {"safe_review", "fast_auto", "ocr_priority", "voice_priority", "clean_subtitle_only", "music_recut"} <= preset_ids
