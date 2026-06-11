from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.schemas.project_schema import ProjectConfig


def _config(source_dir: Path, output_dir: Path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "retry-preset-test",
            "source_folder": str(source_dir),
            "output_folder": str(output_dir),
            "product": {"name": "x", "brand": "", "description": "x", "features": ["x"], "cta": "x"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 0, "speed_variation": 0, "grain": 0, "zoom_motion": 0, "overlay_height": 22, "subtitle_size": 54},
            "ai": {"text_model": "mock", "tone": "translator", "language": "vi", "gemini_api_keys": []},
            "douyin_reup": DouyinReupSettings(enabled=True, preset_id="safe_review", preset_name="Safe Review").model_dump(mode="json"),
        }
    )


def test_retry_with_preset_queues_selected_failed_outputs_and_settings(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "retry-preset.db"
    database.init_db()
    project = _config(tmp_path / "source", tmp_path / "out")
    database.create_project("project-retry-preset", project.model_dump(mode="json"))
    database.create_job("job-original", "project-retry-preset", preview_only=False, total_outputs=2)
    database.update_job(
        "job-original",
        results_json=json.dumps(
            {
                "outputs": [
                    {"index": 1, "status": "failed", "path": "", "source_video": "a.mp4", "failed_step": "asr", "preset_id": "fast_auto", "preset_name": "Fast Auto"},
                    {"index": 2, "status": "failed", "path": "", "source_video": "b.mp4", "failed_step": "render", "preset_id": "fast_auto", "preset_name": "Fast Auto"},
                ]
            }
        ),
    )
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    captured = {}

    def fake_queue(**kwargs):
        captured.update(kwargs)
        return "job-retry-preset"

    monkeypatch.setattr("app.api._queue_douyin_retry_failed_job", fake_queue)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/douyin-reup/jobs/job-original/retry-with-preset",
            json={
                "preset_id": "ocr_priority",
                "video_ids": ["video_001"],
                "retry_steps": ["asr"],
                "settings": {"ocr_sample_fps": 3.0},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-retry-preset"
    assert payload["retry_outputs"] == 1
    assert captured["failed_outputs"][0]["source_video"] == "a.mp4"
    assert captured["retry_steps"] == {"asr"}
    assert captured["settings_override"]["preset_id"] == "ocr_priority"
    assert captured["settings_override"]["ocr_sample_fps"] == 3.0


def test_retry_with_preset_allows_selected_success_output_for_mode_change(tmp_path: Path, monkeypatch):
    database.DB_PATH = tmp_path / "retry-success.db"
    database.init_db()
    project = _config(tmp_path / "source", tmp_path / "out")
    database.create_project("project-success", project.model_dump(mode="json"))
    database.create_job("job-success", "project-success", preview_only=False, total_outputs=1)
    database.update_job(
        "job-success",
        results_json=json.dumps(
            {"outputs": [{"index": 1, "status": "success", "path": "out.mp4", "source_video": "source.mp4"}]}
        ),
    )
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)
    captured = {}
    monkeypatch.setattr(
        "app.api._queue_douyin_retry_failed_job",
        lambda **kwargs: captured.update(kwargs) or "job-mode-change",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/douyin-reup/jobs/job-success/retry-with-preset",
            json={"preset_id": "silent_product_voiceover", "video_ids": ["video_001"]},
        )

    assert response.status_code == 200
    assert response.json()["retry_outputs"] == 1
    assert captured["failed_outputs"][0]["status"] == "success"
    assert captured["settings_override"]["generate_voiceover_for_silent_video"] is True
