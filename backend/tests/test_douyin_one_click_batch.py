from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.douyin_reup.douyin_schema import DouyinVideoItem


def test_douyin_one_click_batch_queues_job_with_preset_settings(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "one-click.db"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "out"
    music_dir = tmp_path / "music"
    source_dir.mkdir()
    output_dir.mkdir()
    music_dir.mkdir()
    (music_dir / "bgm.mp3").write_bytes(b"fake-audio")
    video = source_dir / "clip.mp4"
    video.write_bytes(b"fake")

    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    monkeypatch.setattr("app.api.run_douyin_reup_job", lambda _job_id: None)

    class FakeScanner:
        def scan_folder(self, _folder):
            return [
                DouyinVideoItem(
                    path=str(video),
                    filename=video.name,
                    duration=8,
                    width=1080,
                    height=1920,
                    fps=30,
                    has_audio=True,
                    embedded_subtitle_found=False,
                )
            ]

    monkeypatch.setattr("app.api.DouyinFolderScanner", FakeScanner)

    with TestClient(create_app()) as client:
        client.put(
            "/api/settings",
            json={
                "gemini_api_keys": ["test-gemini-key"],
                "google_tts_credentials_json_path": None,
                "google_tts_api_key": None,
                "google_tts_access_token": None,
            },
        )
        response = client.post(
            "/api/douyin-reup/one-click",
            json={
                "project_name": "one-click-test",
                "source_folder": str(source_dir),
                "output_folder": str(output_dir),
                "preset_id": "fast_auto",
                "bgm_folder": str(music_dir),
                "process_mode": "first_n",
                "max_videos": 1,
                "advanced_overrides": {
                    "bgm_volume": 0.2,
                    "batch_performance_mode": "balanced",
                    "batch_chunk_size": 40,
                    "batch_ffmpeg_timeout_seconds": 600,
                    "batch_watchdog_stale_minutes": 15,
                    "asr_max_audio_seconds": 90,
                    "ocr_region_mode": "full_frame",
                    "ocr_sample_fps": 3.0,
                    "prefer_ocr_over_asr_when_text_visible": True,
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["preset_id"] == "fast_auto"
    assert payload["total_outputs"] == 1

    job = database.get_job(payload["job_id"])
    assert job is not None
    project = database.get_project(job["project_id"])
    settings = project["config"]["douyin_reup"]
    assert settings["preset_id"] == "fast_auto"
    assert settings["process_mode"] == "first_n"
    assert settings["music_folder"] == str(music_dir.resolve())
    assert settings["bgm_volume"] == 0.2
    assert settings["asr_model_size"] == "tiny"
    assert settings["asr_vad_filter"] is True
    assert settings["asr_max_audio_seconds"] == 90
    assert settings["ocr_region_mode"] == "full_frame"
    assert settings["ocr_sample_fps"] == 3.0
    assert settings["ocr_min_confidence"] == 0.35
    assert settings["prefer_ocr_over_asr_when_text_visible"] is True
    assert settings["batch_performance_mode"] == "balanced"
    assert settings["batch_chunk_size"] == 40
    assert settings["batch_ffmpeg_timeout_seconds"] == 600
    assert settings["batch_watchdog_stale_minutes"] == 15
