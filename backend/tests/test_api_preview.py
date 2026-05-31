from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.script_writer.script_writer import ProductVideoScript


def _config(tmp_path: Path) -> dict:
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "outputs"
    source_dir.mkdir()
    return {
        "project_name": "api-preview-test",
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
            "output_count": 3,
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
        },
    }


def _script() -> dict:
    return {
        "hook": "Hook custom",
        "voiceover": [{"time_hint": "0-4s", "text": "Đây là câu test."}],
        "subtitles": [{"start_hint": 0, "end_hint": 4, "text": "Đây là câu test."}],
        "cta": "Xem ngay",
        "caption": "Caption test",
        "hashtags": ["#test"],
    }


def test_project_render_preview_api_flow(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "autotool-test.db"

    def fake_render_project(
        config,
        preview_only=False,
        custom_script=None,
        progress_callback=None,
        log_callback=None,
    ):
        assert preview_only is True
        output_dir = Path(config.output_folder) / "preview"
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / "preview_001.mp4"
        script_path = output_dir / "preview_001_script.json"
        subtitle_path = output_dir / "preview_001_sub.srt"
        voice_path = output_dir / "preview_001_voice.wav"
        log_path = output_dir / "preview_001_log.json"
        script = custom_script or ProductVideoScript.model_validate(_script())

        final_path.write_bytes(b"fake mp4")
        script_path.write_text(json.dumps(script.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8")
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:04,000\nĐây là câu test.\n", encoding="utf-8")
        voice_path.write_bytes(b"fake wav")
        log_path.write_text('{"status":"success"}', encoding="utf-8")
        if progress_callback:
            progress_callback(
                {
                    "current_step": "completed",
                    "progress": 100,
                    "total_outputs": 1,
                    "completed_outputs": 1,
                    "failed_outputs": 0,
                }
            )

        return {
            "project_name": config.project_name,
            "created_at": "2026-05-31T00:00:00",
            "source_folder": config.source_folder,
            "output_folder": str(output_dir),
            "total_input_videos": 1,
            "total_segments": 1,
            "requested_outputs": 1,
            "total_outputs": 1,
            "successful_outputs": 1,
            "failed_outputs": 0,
            "warnings_count": 0,
            "failed_items": [],
            "outputs": [
                {
                    "index": 1,
                    "path": str(final_path),
                    "status": "success",
                    "duration": 4,
                    "script_file": str(script_path),
                    "subtitle_file": str(subtitle_path),
                    "voice_file": str(voice_path),
                    "log_file": str(log_path),
                    "timeline_template": config.timeline.template_id,
                    "script_variant_id": script.variant_style_id,
                    "caption": script.caption,
                    "hashtags": list(script.hashtags),
                    "warnings": [],
                    "errors": [],
                }
            ],
        }

    monkeypatch.setattr("app.api.render_project", fake_render_project)

    with TestClient(create_app()) as client:
        templates = client.get("/api/timeline-templates")
        assert templates.status_code == 200
        assert any(item["id"] == "ugc_reviewer_natural" for item in templates.json()["templates"])

        created = client.post("/api/projects", json=_config(tmp_path))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        saved = client.put(f"/api/projects/{project_id}/script", json=_script())
        assert saved.status_code == 200
        assert saved.json()["script"]["hook"] == "Hook custom"

        queued = client.post(f"/api/projects/{project_id}/render", json={"preview_only": True})
        assert queued.status_code == 200
        job_id = queued.json()["job_id"]

        for _ in range(20):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            time.sleep(0.05)

        assert job["status"] == "completed"
        assert job["total_outputs"] == 1
        assert job["completed_outputs"] == 1

        results = client.get(f"/api/jobs/{job_id}/results").json()
        output = results["outputs"][0]
        assert output["path"].endswith("preview_001.mp4")
        assert output["caption"] == "Caption test"
        assert output["hashtags"] == ["#test"]
        assert output["timeline_template"] == "ugc_reviewer_natural"

        latest_script = client.get(f"/api/projects/{project_id}/latest-script").json()
        assert latest_script["script"]["hook"] == "Hook custom"

        file_response = client.get("/api/files/video", params={"path": output["path"]})
        assert file_response.status_code == 200

        unregistered = tmp_path / "unregistered.mp4"
        unregistered.write_bytes(b"not an output")
        denied = client.get("/api/files/video", params={"path": str(unregistered)})
        assert denied.status_code == 403
