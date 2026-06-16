from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app import database
from app.modules.queue_control import QueueItemStatus, QueueSettings, QueueStateService, QueueWatchdogService


def test_queue_watchdog_marks_stale_running_item_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=1)
    state_service = QueueStateService(storage_root=tmp_path / "queue")
    state = state_service.create_queue_state(
        "job-1",
        "douyin_reup",
        [str(tmp_path / "a.mp4")],
        QueueSettings(watchdog_stale_minutes=5),
        str(tmp_path / "out"),
        "project-1",
    )
    stale_time = (datetime.now() - timedelta(minutes=10)).replace(microsecond=0).isoformat()
    state = state_service.update_item_status(
        "job-1",
        state.items[0].id,
        QueueItemStatus.running,
        current_step="asr_transcribing",
        progress_percent=30,
    )
    state.items[0] = state.items[0].model_copy(update={"updated_at": stale_time})
    state_service.save_queue_state(state)

    service = QueueWatchdogService(state_service)
    first = service.inspect("job-1")
    second = service.inspect("job-1")

    assert first["messages"]
    assert second["messages"] == first["messages"]
    reloaded = state_service.load_queue_state("job-1")
    assert reloaded is not None
    assert reloaded.items[0].status == QueueItemStatus.running
    assert reloaded.items[0].current_step == "watchdog_stale"
    assert len(database.get_job_logs("job-1")) == 1


def test_queue_watchdog_can_fail_stale_item_when_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=1)
    state_service = QueueStateService(storage_root=tmp_path / "queue")
    state = state_service.create_queue_state(
        "job-1",
        "douyin_reup",
        [str(tmp_path / "a.mp4")],
        QueueSettings(watchdog_stale_minutes=5, auto_fail_stale_items=True),
        str(tmp_path / "out"),
        "project-1",
    )
    stale_time = (datetime.now() - timedelta(minutes=10)).replace(microsecond=0).isoformat()
    state = state_service.update_item_status(
        "job-1",
        state.items[0].id,
        QueueItemStatus.running,
        current_step="ffmpeg_render",
        progress_percent=50,
    )
    state.items[0] = state.items[0].model_copy(update={"updated_at": stale_time})
    state_service.save_queue_state(state)

    QueueWatchdogService(state_service).inspect("job-1")

    reloaded = state_service.load_queue_state("job-1")
    assert reloaded is not None
    assert reloaded.items[0].status == QueueItemStatus.failed
    assert reloaded.failed_items == 1
