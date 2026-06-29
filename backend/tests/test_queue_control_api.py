import os
from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app import database
from app.api import create_app
from app.modules.job_recovery import ResumeJobResult
from app.modules.queue_control import QueueRunStatus, QueueSettings, QueueStateService


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


def test_resume_resuming_queue_starts_recovery_worker(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    monkeypatch.setenv("AUTO_TOOL_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setattr(api_module, "start_background_dependency_warmup", lambda **_: None)
    database.init_db()
    database.create_project("project-1", {"project_name": "demo", "douyin_reup": {"enabled": True}})
    database.create_job("job-resume", "project-1", preview_only=False, total_outputs=2)
    database.update_job("job-resume", status="resuming", current_step="resuming")
    queue_service = QueueStateService()
    state = queue_service.create_queue_state(
        job_id="job-resume",
        mode="douyin_reup",
        video_paths=["a.mp4", "b.mp4"],
        settings=QueueSettings(),
        output_dir=str(tmp_path / "outputs"),
        project_id="project-1",
    )
    queue_service.save_queue_state(state.model_copy(update={"status": QueueRunStatus.resuming}))
    resume_calls = []

    def fake_resume_job(self, request):
        del self
        resume_calls.append(request)
        return ResumeJobResult(
            success=True,
            original_job_id=request.job_id,
            resumed_items=1,
            resume_plan={"selected_source_videos": ["b.mp4"], "pending_outputs": []},
        )

    monkeypatch.setattr(api_module.JobResumeService, "resume_job", fake_resume_job)

    with TestClient(create_app()) as client:
        response = client.post("/api/queue-control/jobs/job-resume/resume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "resume_job" in payload["data"]
    assert len(resume_calls) == 1
    assert resume_calls[0].resume_mode == "reconcile_then_continue"
