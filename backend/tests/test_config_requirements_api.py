from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
import app.api as api_module


def test_config_requirements_blocks_missing_gemini(tmp_path: Path, monkeypatch) -> None:
    _isolated_config_env(tmp_path, monkeypatch)
    with TestClient(api_module.create_app()) as client:
        response = client.post("/api/config/requirements", json={"mode": "product_render"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["errors_count"] == 1
    assert payload["issues"][0]["code"] == "missing_gemini_api_key"


def test_config_requirements_accepts_gemini_from_app_settings(tmp_path: Path, monkeypatch) -> None:
    _isolated_config_env(tmp_path, monkeypatch)
    with TestClient(api_module.create_app()) as client:
        client.put(
            "/api/settings",
            json={
                "gemini_api_keys": ["test-gemini-key"],
                "google_tts_credentials_json_path": None,
                "google_tts_api_key": None,
                "google_tts_access_token": None,
            },
        )
        response = client.post("/api/config/requirements", json={"mode": "product_render"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["issues"] == []


def test_config_requirements_reports_missing_google_tts_credentials_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _isolated_config_env(tmp_path, monkeypatch)
    config = _project_config(tmp_path)
    config["ai"]["gemini_api_keys"] = ["test-gemini-key"]
    config["tts"] = {
        "provider": "google_cloud_tts",
        "fallback_provider": "piper",
        "voice": "vi-VN-Wavenet-A",
        "language": "vi",
        "api_key": None,
        "credentials_json_path": str(tmp_path / "missing-service-account.json"),
        "access_token": None,
        "rate": "+0%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "output_format": "mp3",
    }

    with TestClient(api_module.create_app()) as client:
        response = client.post(
            "/api/config/requirements",
            json={"mode": "product_render", "project_config": config},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["issues"][0]["code"] == "google_tts_credentials_file_missing"


def _isolated_config_env(tmp_path: Path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "autotool-config-requirements.db"
    monkeypatch.setattr(api_module, "load_local_env", lambda: None)
    for key in (
        "GEMINI_API_KEY",
        "GEMINI_API_KEYS",
        "GOOGLE_TTS_API_KEY",
        "GOOGLE_CLOUD_TTS_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_TTS_CREDENTIALS_JSON_PATH",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_TTS_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    return {
        "project_name": "config-requirements-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "San pham test",
            "brand": "Brand",
            "description": "Mo ta test.",
            "features": ["Tinh nang test"],
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
    }
