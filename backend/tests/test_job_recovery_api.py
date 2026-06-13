import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app import database
from app.api import create_app


def test_job_recovery_api_lists_reconciles_and_marks_cancelled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    monkeypatch.setattr(api_module, "start_background_dependency_warmup", lambda **_: None)
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=1)
    output = tmp_path / "output.txt"
    output.write_text("ok", encoding="utf-8")
    database.update_job(
        "job-1",
        status="running",
        current_step="rendering_video_1",
        completed_outputs=1,
        output_folder=str(tmp_path),
        results_json=json.dumps({"outputs": [{"index": 1, "path": str(output), "status": "success"}]}),
    )

    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["recoverable_jobs_count"] >= 1

        candidates = client.get("/api/job-recovery/candidates")
        assert candidates.status_code == 200
        assert candidates.json()["data"]["items"]

        detail = client.get("/api/job-recovery/jobs/job-1")
        assert detail.status_code == 200
        assert detail.json()["data"]["candidate"]["job_id"] == "job-1"

        reconciled = client.post("/api/job-recovery/jobs/job-1/reconcile")
        assert reconciled.status_code == 200
        assert reconciled.json()["data"]["completed_items"] == 1

        cancelled = client.post("/api/job-recovery/jobs/job-1/mark-cancelled")
        assert cancelled.status_code == 200
        assert database.get_job("job-1")["status"] == "cancelled"

