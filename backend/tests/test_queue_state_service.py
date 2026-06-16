from pathlib import Path

from app.modules.queue_control import QueueItemStatus, QueueSettings, QueueStateService


def test_queue_state_service_creates_updates_and_mirrors_files(tmp_path: Path):
    output_dir = tmp_path / "outputs"
    service = QueueStateService(storage_root=tmp_path / "queue")

    state = service.create_queue_state(
        job_id="job-1",
        mode="product_render",
        video_paths=[str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")],
        settings=QueueSettings(),
        output_dir=str(output_dir),
        project_id="project-1",
    )

    assert state.total_items == 2
    assert state.concurrency_plan is not None
    assert state.concurrency_plan.effective_concurrency == 1
    assert service.queue_state_path("job-1").exists()
    assert (output_dir / "queue_state.json").exists()
    assert (output_dir / "queue_items.json").exists()

    updated = service.update_item_status(
        "job-1",
        "job-1:item:001",
        QueueItemStatus.completed,
        current_step="completed",
        progress_percent=100,
        output_video_path=str(output_dir / "video_001.mp4"),
    )

    assert updated.completed_items == 1
    assert updated.items[0].output_video_path.endswith("video_001.mp4")


def test_queue_state_service_respects_max_videos_per_batch(tmp_path: Path):
    service = QueueStateService(storage_root=tmp_path / "queue")
    state = service.create_queue_state(
        job_id="job-limit",
        mode="douyin_reup",
        video_paths=["a.mp4", "b.mp4", "c.mp4"],
        settings=QueueSettings(max_videos_per_batch=2),
        output_dir=str(tmp_path / "out"),
    )

    assert state.total_items == 2
    assert [item.video_id for item in state.items] == ["video_001", "video_002"]


def test_queue_state_service_clamps_parallel_request_until_worker_pool_is_safe(tmp_path: Path):
    service = QueueStateService(storage_root=tmp_path / "queue")
    state = service.create_queue_state(
        job_id="job-parallel",
        mode="douyin_reup",
        video_paths=["a.mp4", "b.mp4", "c.mp4"],
        settings=QueueSettings(
            max_concurrent_videos=2,
            allow_parallel_asr=True,
            allow_parallel_ocr=True,
            allow_parallel_render=True,
        ),
        output_dir=str(tmp_path / "out"),
    )

    assert state.settings.max_concurrent_videos == 1
    assert state.concurrency_plan is not None
    assert state.concurrency_plan.requested_concurrency == 2
    assert state.concurrency_plan.effective_concurrency == 1
    assert state.concurrency_plan.worker_pool_enabled is False
    assert state.warnings
