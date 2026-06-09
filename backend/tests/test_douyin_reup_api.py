from __future__ import annotations

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.douyin_reup.douyin_schema import DouyinVideoItem


def test_douyin_reup_scan_and_process_api_queue_job(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-douyin-test.db"
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    video = source_dir / "clip.mp4"
    video.write_bytes(b"fake")

    class FakeScanner:
        def __init__(self):
            self.total_files = 1
            self.invalid_files = 0
            self.errors = []

        def scan_folder(self, folder):
            return [
                DouyinVideoItem(
                    path=str(video.resolve()),
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
    monkeypatch.setattr("app.api.run_douyin_reup_job", lambda job_id: None)

    with TestClient(create_app()) as client:
        scan = client.post("/api/douyin-reup/scan", json={"source_folder": str(source_dir)})
        assert scan.status_code == 200
        assert scan.json()["valid_videos"] == 1

        queued = client.post(
            "/api/douyin-reup/process",
            json={
                "project_name": "douyin-api-test",
                "source_folder": str(source_dir),
                "output_folder": str(output_dir),
                "settings": {
                    "enabled": True,
                    "source_language": "zh",
                    "target_language": "vi",
                    "translation_provider": "gemini",
                    "subtitle_source_priority": ["sidecar_srt", "embedded_subtitle", "asr"],
                    "use_sidecar_srt": True,
                    "use_embedded_subtitle": True,
                    "use_asr_if_no_subtitle": False,
                    "asr_provider": "faster_whisper",
                    "asr_model_size": "medium",
                    "asr_device": "auto",
                    "visual_style_preset_id": "clean_review_light",
                    "burn_subtitle": True,
                    "add_overlay": True,
                    "music_folder": None,
                    "bgm_volume": 0.16,
                    "original_audio_volume": 0.85,
                    "duck_bgm_when_voice": False,
                    "resolution": "1080x1920",
                    "fps": 30,
                    "process_mode": "all",
                    "max_videos": None,
                    "selected_video_paths": [],
                    "keep_temp": False,
                },
            },
        )
        assert queued.status_code == 200
        payload = queued.json()
        assert payload["status"] == "queued"
        assert payload["job_id"]

        job = client.get(f"/api/jobs/{payload['job_id']}")
        assert job.status_code == 200
        assert job.json()["total_outputs"] == 1

        results = client.get(f"/api/douyin-reup/jobs/{payload['job_id']}/results")
        assert results.status_code == 200
        assert results.json()["outputs"] == []
