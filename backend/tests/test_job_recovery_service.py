from pathlib import Path

from app import database
from app.modules.job_recovery import JobCheckpointService, JobRecoveryService, JobRunStatus


def test_startup_marks_running_job_recoverable(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=3)
    database.update_job("job-1", status="running", current_step="rendering_video_2", completed_outputs=1)
    service = JobRecoveryService(JobCheckpointService(tmp_path / "recovery"))

    candidates = service.mark_interrupted_jobs_on_startup()

    assert len(candidates) == 1
    assert candidates[0].status == JobRunStatus.recoverable
    assert candidates[0].completed_items == 1
    assert database.get_job("job-1")["status"] == "recoverable"

