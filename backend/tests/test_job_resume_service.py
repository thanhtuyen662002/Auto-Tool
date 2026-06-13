import json
from pathlib import Path

from app import database
from app.modules.job_recovery import JobCheckpointService, JobLockService, JobReconciliationService, JobResumeService, ResumeJobRequest


def test_resume_creates_manifest_and_does_not_overwrite_completed(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=2)
    output = tmp_path / "video_001.txt"
    output.write_text("ok", encoding="utf-8")
    database.update_job(
        "job-1",
        status="recoverable",
        completed_outputs=1,
        output_folder=str(tmp_path),
        results_json=json.dumps({"outputs": [{"index": 1, "path": str(output), "status": "success"}]}),
    )
    service = JobResumeService(
        reconciliation_service=JobReconciliationService(),
        checkpoint_service=JobCheckpointService(tmp_path / "recovery"),
        lock_service=JobLockService(tmp_path / "locks"),
    )

    result = service.resume_job(ResumeJobRequest(job_id="job-1"))

    assert result.success
    assert result.new_job_id
    assert result.skipped_completed_items == 1
    assert result.resumed_items == 1
    assert result.resume_manifest_path and Path(result.resume_manifest_path).exists()
    assert database.get_job(result.new_job_id)["status"] == "queued"
    assert service.locks.is_job_locked("job-1")

