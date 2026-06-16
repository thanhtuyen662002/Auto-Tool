import json
from pathlib import Path

from app import database
from app.modules.job_recovery import JobCheckpointService, JobLockService, JobReconciliationService, JobResumeService, ResumeJobRequest
from app.modules.queue_control import QueueItemStatus, QueueSettings, QueueStateService


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


def test_resume_plan_uses_queue_source_paths_for_douyin_pending_items(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    monkeypatch.setattr("app.modules.queue_control.queue_state_service.app_data_dir", lambda: tmp_path / "appdata")
    database.init_db()
    database.create_project("project-queue", {"project_name": "douyin"})
    database.create_job("job-queue", "project-queue", preview_only=False, total_outputs=3)
    completed_output = tmp_path / "done.txt"
    completed_output.write_bytes(b"done")
    database.update_job(
        "job-queue",
        status="paused",
        completed_outputs=1,
        output_folder=str(tmp_path / "outputs"),
        results_json=json.dumps({"outputs": [{"index": 1, "path": str(completed_output), "status": "success"}]}),
    )
    queue_service = QueueStateService()
    queue_service.create_queue_state(
        job_id="job-queue",
        mode="douyin_reup",
        video_paths=["a.mp4", "b.mp4", "c.mp4"],
        settings=QueueSettings(),
        output_dir=str(tmp_path / "outputs"),
        project_id="project-queue",
    )
    queue_service.update_item_status("job-queue", "job-queue:item:001", QueueItemStatus.completed, output_video_path=str(completed_output))
    queue_service.update_item_status("job-queue", "job-queue:item:002", QueueItemStatus.paused, current_step="asr")

    service = JobResumeService(
        reconciliation_service=JobReconciliationService(),
        checkpoint_service=JobCheckpointService(tmp_path / "recovery"),
        lock_service=JobLockService(tmp_path / "locks"),
    )

    plan = service.build_resume_plan("job-queue", ResumeJobRequest(job_id="job-queue", resume_mode="reconcile_then_continue"))

    assert plan["resumed_items"] == 2
    assert plan["selected_source_videos"] == ["b.mp4", "c.mp4"]
    assert [item["source_video"] for item in plan["retry_outputs"]] == ["b.mp4"]
    assert [item["source_video"] for item in plan["pending_outputs"]] == ["c.mp4"]
