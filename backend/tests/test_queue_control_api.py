import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app import database
from app.api import create_app


def test_queue_control_api_lifecycle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setattr(api_module, "start_background_dependency_warmup", lambda **_: None)
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=2)

    with TestClient(create_app()) as client:
        state = client.get("/api/queue-control/jobs/job-1")
        assert state.status_code == 200
        assert state.json()["data"]["total_items"] == 2

        paused = client.post("/api/queue-control/jobs/job-1/pause")
        assert paused.status_code == 200
        assert paused.json()["success"] is True

        skipped = client.post(
            "/api/queue-control/jobs/job-1/skip-selected",
            json={"item_ids": ["job-1:item:002"]},
        )
        assert skipped.status_code == 200
        assert skipped.json()["affected_items"] == 1

        resource = client.get("/api/queue-control/jobs/job-1/resource-status")
        assert resource.status_code == 200
        assert resource.json()["success"] is True

        cancelled = client.post("/api/queue-control/jobs/job-1/cancel")
        assert cancelled.status_code == 200
        assert database.get_job("job-1")["status"] == "cancel_requested"
