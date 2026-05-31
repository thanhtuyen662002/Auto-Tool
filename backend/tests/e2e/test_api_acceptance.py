from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.tts.tts_schema import TTSVoiceInfo

from tests.e2e.helpers import (
    assert_no_raw_traceback,
    load_json,
    patch_fast_tts,
    wait_for_job,
    write_project_config,
)


def _api_payload(config_path: Path) -> dict:
    payload = load_json(config_path)
    payload["source_folder"] = str(config_path.parent / "sample_videos" / "sample_product")
    payload["output_folder"] = str(config_path.parent / "outputs")
    return payload


def test_api_project_scan_preview_render_and_results(tmp_path, monkeypatch):
    patch_fast_tts(monkeypatch)
    monkeypatch.setattr(
        "app.api.list_google_cloud_voices",
        lambda api_key=None, language_code="vi-VN", credentials_json_path=None, access_token=None: [
            TTSVoiceInfo(
                name="vi-VN-Wavenet-A",
                language_codes=["vi-VN"],
                ssml_gender="FEMALE",
                natural_sample_rate_hertz=24000,
            )
        ],
    )
    database.DB_PATH = tmp_path / "autotool-api-e2e.db"
    config_path = write_project_config(tmp_path, output_count=2, duration=4.0, source_count=3)

    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        presets = client.get("/api/presets")
        assert presets.status_code == 200
        assert any(item["name"] == "Balanced Recut" for item in presets.json())

        templates = client.get("/api/timeline-templates")
        assert templates.status_code == 200
        assert any(item["id"] == "ugc_reviewer_natural" for item in templates.json()["templates"])

        variant_styles = client.get("/api/script-variants/styles")
        assert variant_styles.status_code == 200
        assert len(variant_styles.json()["styles"]) >= 6

        tts_providers = client.get("/api/tts/providers")
        assert tts_providers.status_code == 200
        provider_ids = {provider["id"] for provider in tts_providers.json()["providers"]}
        assert {"edge_tts", "google_cloud_tts", "piper", "gtts", "silent"}.issubset(provider_ids)

        google_voices = client.post(
            "/api/tts/google-cloud/voices",
            json={"api_key": "test-key", "language_code": "vi-VN"},
        )
        assert google_voices.status_code == 200
        assert google_voices.json()["voices"][0]["name"] == "vi-VN-Wavenet-A"

        created = client.post("/api/projects", json=_api_payload(config_path))
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        scanned = client.post(f"/api/projects/{project_id}/scan")
        assert scanned.status_code == 200
        scan_payload = scanned.json()
        assert scan_payload["total_files"] == 3
        assert scan_payload["valid_videos"] == 3
        assert scan_payload["invalid_files"] == 0

        generated = client.post(
            f"/api/projects/{project_id}/generate-script-variants",
            json={"output_count": 2, "timeline_template_id": "ugc_reviewer_natural"},
        )
        assert generated.status_code == 200
        assert generated.json()["total_variants"] == 2

        queued = client.post(f"/api/projects/{project_id}/render", json={"preview_only": True})
        assert queued.status_code == 200
        assert queued.json()["status"] == "queued"
        job_id = queued.json()["job_id"]

        job = wait_for_job(client, job_id)
        assert job["status"] == "completed"
        assert job["progress"] == 100
        assert job["total_outputs"] == 1
        assert job["completed_outputs"] == 1
        assert job["failed_outputs"] == 0
        assert job["logs"]

        results = client.get(f"/api/jobs/{job_id}/results")
        assert results.status_code == 200
        outputs = results.json()["outputs"]
        assert len(outputs) == 1
        assert outputs[0]["path"].endswith("preview_001.mp4")
        assert Path(outputs[0]["path"]).exists()
        assert Path(outputs[0]["normalized_voice_file"]).exists()
        assert outputs[0]["caption"]
        assert isinstance(outputs[0]["hashtags"], list)
        assert outputs[0]["timeline_template"] == "ugc_reviewer_natural"

        output_log = load_json(outputs[0]["log_file"])
        assert output_log["tts"]["normalized_voice_path"].endswith("_voice_normalized.wav")
        assert output_log["tts"]["voice_duration"] > 0
        assert output_log["subtitle_sync"]["subtitle_active_duration"] is not None

        latest = client.get(f"/api/projects/{project_id}/latest-script")
        assert latest.status_code == 200
        assert latest.json()["script"]["voiceover"]


def test_api_errors_are_clear_and_do_not_return_raw_traceback(tmp_path):
    database.DB_PATH = tmp_path / "autotool-api-error.db"
    config_path = write_project_config(tmp_path, output_count=1, duration=4.0, source_count=1)
    payload = _api_payload(config_path)
    payload["source_folder"] = str(tmp_path / "missing-source-folder")

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=payload)
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        scanned = client.post(f"/api/projects/{project_id}/scan")
        assert scanned.status_code == 400
        body = scanned.json()
        assert "Source folder does not exist" in body["detail"]
        assert_no_raw_traceback(body)

        missing_job = client.get("/api/jobs/not-a-real-job")
        assert missing_job.status_code == 404
        assert "Job not found" in missing_job.json()["detail"]
        assert_no_raw_traceback(missing_job.json())
