from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
import app.api as api_module
from app.schemas.project_schema import ProjectConfig


def test_app_settings_persists_voice_and_music_favorites(tmp_path: Path, monkeypatch) -> None:
    _isolated_env(tmp_path, monkeypatch)
    music_file = tmp_path / "music" / "track.mp3"
    music_file.parent.mkdir()
    music_file.write_bytes(b"fake-audio")

    with TestClient(api_module.create_app()) as client:
        response = client.put(
            "/api/settings",
            json={
                "gemini_api_keys": ["gemini-1"],
                "google_tts_credentials_json_path": None,
                "google_tts_api_key": "google-key",
                "google_tts_access_token": None,
                "google_tts_favorite_voices": ["vi-VN-Wavenet-A", "vi-VN-Neural2-A"],
                "google_tts_preview_text": "Xin chào Auto Tool.",
                "favorite_music_paths": [str(music_file)],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["google_tts_favorite_voices"] == ["vi-VN-Wavenet-A", "vi-VN-Neural2-A"]
    assert payload["favorite_music_paths"] == [str(music_file)]


def test_music_library_marks_favorite_tracks(tmp_path: Path, monkeypatch) -> None:
    _isolated_env(tmp_path, monkeypatch)
    music_folder = tmp_path / "music"
    music_folder.mkdir()
    favorite = music_folder / "favorite.mp3"
    regular = music_folder / "regular.wav"
    favorite.write_bytes(b"fake-audio")
    regular.write_bytes(b"fake-audio")
    monkeypatch.setattr(api_module, "probe_media_duration", lambda path: 12.345)

    with TestClient(api_module.create_app()) as client:
        client.put(
            "/api/settings",
            json={
                "gemini_api_keys": [],
                "google_tts_credentials_json_path": None,
                "google_tts_api_key": None,
                "google_tts_access_token": None,
                "google_tts_favorite_voices": [],
                "google_tts_preview_text": "Xin chào.",
                "favorite_music_paths": [str(favorite)],
            },
        )
        response = client.get("/api/music/library", params={"folder_path": str(music_folder)})

    assert response.status_code == 200
    tracks = response.json()["tracks"]
    assert len(tracks) == 2
    favorite_track = next(item for item in tracks if item["filename"] == "favorite.mp3")
    regular_track = next(item for item in tracks if item["filename"] == "regular.wav")
    assert favorite_track["favorite"] is True
    assert favorite_track["duration"] == 12.345
    assert regular_track["favorite"] is False


def test_apply_app_settings_injects_favorite_voice_and_music(tmp_path: Path, monkeypatch) -> None:
    _isolated_env(tmp_path, monkeypatch)
    favorite_music = tmp_path / "music" / "priority.mp3"
    favorite_music.parent.mkdir()
    favorite_music.write_bytes(b"fake-audio")
    database.init_db()
    database.update_app_settings(
        {
            "gemini_api_keys": [],
            "google_tts_credentials_json_path": None,
            "google_tts_api_key": "google-key",
            "google_tts_access_token": None,
            "google_tts_favorite_voices": ["vi-VN-Wavenet-A"],
            "google_tts_preview_text": "Xin chào.",
            "favorite_music_paths": [str(favorite_music)],
        }
    )

    config = ProjectConfig.model_validate(_project_config(tmp_path))
    applied = api_module._apply_app_settings(config)

    assert applied.tts.provider == "google_cloud_tts"
    assert applied.tts.voice == "vi-VN-Wavenet-A"
    assert applied.tts.api_key == "google-key"
    assert applied.music.favorite_music_paths == [str(favorite_music)]


def _isolated_env(tmp_path: Path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "voice-music-library.db"
    monkeypatch.setattr(api_module, "load_local_env", lambda: None)


def _project_config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir(exist_ok=True)
    return {
        "project_name": "voice-music-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Sản phẩm test",
            "brand": "Brand",
            "description": "Mô tả test.",
            "features": ["Tính năng test"],
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
