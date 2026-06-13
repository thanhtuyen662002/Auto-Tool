from pathlib import Path

from app.modules.queue_control import QueueItemStatus, QueueRetryService, QueueSettings, QueueStateService


def test_queue_retry_service_resets_failed_items(tmp_path: Path):
    state_service = QueueStateService(storage_root=tmp_path / "queue")
    state_service.create_queue_state(
        "job-retry",
        "product_render",
        ["a.mp4"],
        QueueSettings(),
        str(tmp_path / "out"),
    )
    state_service.update_item_status(
        "job-retry",
        "job-retry:item:001",
        QueueItemStatus.failed,
        current_step="render",
        progress_percent=100,
        error_message="FFmpeg failed",
    )

    result = QueueRetryService(state_service).retry_failed_items("job-retry")

    assert result.affected_items == 1
    item = state_service.load_queue_state("job-retry").items[0]
    assert item.status == QueueItemStatus.queued
    assert item.progress_percent == 0
    assert item.previous_errors == ["FFmpeg failed"]
