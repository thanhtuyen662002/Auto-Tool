from pathlib import Path

from app import database
from app.modules.queue_control import QueueControlService, QueueItemStatus, QueueSettings, QueueStateService


def test_queue_control_pause_cancel_and_skip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=2)
    state_service = QueueStateService(storage_root=tmp_path / "queue")
    state_service.create_queue_state(
        "job-1",
        "product_render",
        ["a.mp4", "b.mp4"],
        QueueSettings(),
        str(tmp_path / "out"),
        "project-1",
    )
    service = QueueControlService(state_service)

    pause = service.request_pause("job-1")
    assert pause.success is True
    assert database.get_job("job-1")["status"] == "pausing"
    assert service.should_pause("job-1") is True

    skipped = service.skip_items("job-1", ["job-1:item:002"])
    assert skipped.affected_items == 1
    assert state_service.load_queue_state("job-1").items[1].status == QueueItemStatus.skipped

    cancel = service.request_cancel("job-1")
    assert cancel.success is True
    assert service.should_cancel("job-1") is True
