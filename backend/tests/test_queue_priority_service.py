from pathlib import Path

from app.modules.queue_control import QueueItemPriority, QueuePriorityService, QueueSettings, QueueStateService


def test_queue_priority_service_moves_and_prioritizes_items(tmp_path: Path):
    state_service = QueueStateService(storage_root=tmp_path / "queue")
    state_service.create_queue_state(
        "job-priority",
        "product_render",
        ["a.mp4", "b.mp4", "c.mp4"],
        QueueSettings(),
        str(tmp_path / "out"),
    )
    service = QueuePriorityService(state_service)

    priority = service.prioritize_items("job-priority", ["job-priority:item:003"])
    assert priority.affected_items == 1
    assert state_service.load_queue_state("job-priority").items[2].priority == QueueItemPriority.high

    moved = service.move_to_top("job-priority", ["job-priority:item:003"])
    assert moved.affected_items == 1
    state = state_service.load_queue_state("job-priority")
    assert state.items[0].id == "job-priority:item:003"
    assert [item.order_index for item in state.items] == [1, 2, 3]
