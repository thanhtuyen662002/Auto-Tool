import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from tests.final_output_qa_helpers import make_video


def test_final_output_qa_and_export_pack_api(tmp_path, monkeypatch):
    database.DB_PATH = tmp_path / "qa-api.db"
    database.init_db()
    project_id = "project-qa-api"
    job_id = "job-qa-api"
    database.create_project(project_id, {"project_name": "qa-api"})
    database.create_job(job_id, project_id, preview_only=False, total_outputs=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    video = make_video(output_root / "video.mp4")
    srt = output_root / "video.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption goi y.\n", encoding="utf-8")
    log = output_root / "video_001_log.json"
    log.write_text("{}", encoding="utf-8")
    outputs = [{"index": 1, "path": str(video), "status": "success", "source_video": str(video), "translated_srt_file": str(srt), "log_file": str(log), "warnings": [], "errors": []}]
    database.update_job(job_id, output_folder=str(output_root), results_json=json.dumps({"summary": {}, "outputs": outputs}))
    monkeypatch.setattr("app.api.start_background_dependency_warmup", lambda **_kwargs: None)

    with TestClient(create_app()) as client:
        one = client.post("/api/final-output-qa/check", json={"output_video_path": str(video), "platform_target": "tiktok", "subtitle_expected": False})
        job = client.post(f"/api/final-output-qa/jobs/{job_id}/check", json={"platform_target": "tiktok"})
        created = client.post(f"/api/douyin-reup/jobs/{job_id}/export-pack", json={"platform_target": "tiktok", "copy_videos": True, "include_subtitles": True, "include_logs": True, "include_captions": True, "include_posting_checklist": True})
        fetched = client.get(f"/api/douyin-reup/jobs/{job_id}/export-pack")

    assert one.status_code == 200
    assert one.json()["report"]["status"] == "passed"
    assert job.status_code == 200
    assert job.json()["summary"]["total_checked"] == 1
    assert created.status_code == 200
    assert Path(created.json()["export_pack"]["output_dir"]).exists()
    assert fetched.status_code == 200
