from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app import database
from app.api import create_app


def test_output_review_api_returns_summary_and_updates_status(tmp_path):
    client, project_id = _client_with_project_and_output(tmp_path)

    response = client.get(f"/api/projects/{project_id}/outputs/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_outputs"] == 1
    assert payload["outputs"][0]["recommended_action"] == "good"

    update = client.put(
        f"/api/projects/{project_id}/outputs/1/review",
        json={"review_status": "needs_rerender", "user_note": "Render lai video nay"},
    )

    assert update.status_code == 200
    assert update.json()["review_status"] == "needs_rerender"

    response = client.get(f"/api/projects/{project_id}/outputs/review")
    assert response.json()["outputs"][0]["review_status"] == "needs_rerender"


def test_rerender_selected_creates_job_without_deleting_old_output(tmp_path, monkeypatch):
    client, project_id = _client_with_project_and_output(tmp_path)
    old_output = database.get_project_jobs(project_id)[0]["results"]["outputs"][0]["path"]

    def fake_run_rerender_job(job_id: str, request_payload: dict, rerender_outputs: list[int]) -> None:
        assert request_payload["reuse_script"] is True
        assert rerender_outputs == [1]
        new_path = tmp_path / "outputs" / "rerenders" / "run_001" / "video_001.mp4"
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(b"new")
        database.update_job(
            job_id,
            status="completed",
            current_step="completed",
            progress=100,
            completed_outputs=1,
            output_folder=str(new_path.parent),
            results_json=json.dumps(
                {"outputs": [{"index": 1, "path": str(new_path), "status": "success"}]},
                ensure_ascii=False,
            ),
        )

    class ImmediateThread:
        def __init__(self, target, args, daemon=True):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(api_module, "run_rerender_job", fake_run_rerender_job)
    monkeypatch.setattr(api_module.threading, "Thread", ImmediateThread)

    response = client.post(
        f"/api/projects/{project_id}/rerender",
        json={
            "mode": "selected",
            "output_indexes": [1],
            "reuse_script": True,
            "reuse_timeline": False,
            "reuse_settings": True,
        },
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert response.json()["rerender_outputs"] == [1]
    assert Path(old_output).exists()
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed"


def _client_with_project_and_output(tmp_path: Path) -> tuple[TestClient, str]:
    database.DB_PATH = tmp_path / "autotool-api-test.db"
    app = create_app()
    client = TestClient(app)
    database.init_db()

    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    output_dir.mkdir()
    response = client.post("/api/projects", json=_config(source_dir, output_dir))
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    output = _output(output_dir)
    database.create_job("job-review", project_id, preview_only=False, total_outputs=1)
    database.update_job(
        "job-review",
        status="completed",
        output_folder=str(output_dir),
        results_json=json.dumps({"outputs": [output]}, ensure_ascii=False),
    )
    return client, project_id


def _output(output_dir: Path) -> dict:
    final_path = output_dir / "video_001.mp4"
    final_path.write_bytes(b"old")
    subtitle_path = output_dir / "video_001_sub.ass"
    subtitle_path.write_text("subtitle", encoding="utf-8")
    script_path = output_dir / "video_001_script.json"
    script_path.write_text(
        json.dumps(
            {
                "hook": "Hook",
                "voiceover": [{"time_hint": "0-12s", "text": "Voice"}],
                "subtitles": [{"start_hint": 0, "end_hint": 12, "text": "Voice"}],
                "cta": "CTA",
                "caption": "Caption",
                "hashtags": ["#test"],
            }
        ),
        encoding="utf-8",
    )
    timeline_path = output_dir / "video_001_timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "output_index": 1,
                "template_id": "ugc_reviewer_natural",
                "target_duration": 12,
                "average_segment_score": 0.9,
                "source_diversity": {"unique_sources": 2, "total_clips": 2},
                "clips": [
                    {"source_path": "a.mp4", "slot_name": "hook", "text_role": "hook", "segment_score": 0.9},
                    {"source_path": "b.mp4", "slot_name": "cta", "text_role": "cta", "segment_score": 0.9},
                ],
            }
        ),
        encoding="utf-8",
    )
    log_path = output_dir / "video_001_log.json"
    log_path.write_text(
        json.dumps(
            {
                "index": 1,
                "status": "success",
                "script_file": str(script_path),
                "subtitle_ass_file": str(subtitle_path),
                "timeline_file": str(timeline_path),
                "tts_provider": "edge_tts",
                "tts": {"provider_used": "edge_tts", "fallback_used": False, "voice_duration": 12, "warnings": []},
                "qa": {
                    "exists": True,
                    "probe_ok": True,
                    "duration_ok": True,
                    "resolution_ok": True,
                    "has_video_stream": True,
                    "has_audio_stream": True,
                    "warnings": [],
                    "errors": [],
                },
                "warnings": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    return {
        "index": 1,
        "path": str(final_path),
        "status": "success",
        "script_file": str(script_path),
        "subtitle_ass_file": str(subtitle_path),
        "timeline_file": str(timeline_path),
        "log_file": str(log_path),
        "tts_provider": "edge_tts",
        "warnings": [],
        "errors": [],
    }


def _config(source_dir: Path, output_dir: Path) -> dict:
    return {
        "project_name": "api-review-test",
        "source_folder": str(source_dir),
        "output_folder": str(output_dir),
        "product": {
            "name": "Product",
            "brand": "Brand",
            "description": "Description",
            "features": ["Feature"],
            "cta": "CTA",
        },
        "render": {
            "output_count": 1,
            "duration": 12,
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
