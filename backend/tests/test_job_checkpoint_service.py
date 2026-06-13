from pathlib import Path

from app.modules.job_recovery import JobCheckpointService, JobRunStatus, JobStepStatus, RecoverableStep


def test_job_checkpoint_service_creates_and_updates_step(tmp_path: Path):
    service = JobCheckpointService(tmp_path / "recovery")
    output_dir = tmp_path / "outputs"

    checkpoint = service.create_job_checkpoint(
        job_id="job-1",
        mode="douyin_reup",
        project_id="project-1",
        settings_snapshot={"project_name": "demo"},
        output_dir=str(output_dir),
    )
    service.mark_step_started("job-1", "video_001", "clip.mp4", RecoverableStep.render)
    step = service.mark_step_completed(
        "job-1",
        "video_001",
        RecoverableStep.render,
        {"video": str(output_dir / "video_001.mp4")},
    )

    loaded = service.load_job_checkpoint("job-1")
    assert loaded is not None
    assert loaded.mode == "douyin_reup"
    assert checkpoint.settings_snapshot_path
    assert step.status == JobStepStatus.completed
    assert (output_dir / "job_checkpoint.json").exists()
    assert service.load_video_checkpoints("job-1")[0].step == RecoverableStep.render


def test_corrupt_checkpoint_does_not_crash(tmp_path: Path):
    service = JobCheckpointService(tmp_path / "recovery")
    job_dir = service.job_dir("job-bad")
    job_dir.mkdir(parents=True)
    (job_dir / "job_checkpoint.json").write_text("{bad json", encoding="utf-8")

    assert service.load_job_checkpoint("job-bad") is None
    assert list(job_dir.glob("job_checkpoint.json.corrupt.*"))


def test_update_status_creates_minimal_checkpoint(tmp_path: Path):
    service = JobCheckpointService(tmp_path / "recovery")

    checkpoint = service.update_job_status("job-new", JobRunStatus.recoverable, "rendering_video_1")

    assert checkpoint.status == JobRunStatus.recoverable
    assert checkpoint.current_step == RecoverableStep.render

