from __future__ import annotations

from app.modules.queue_control.queue_control_schema import QueueActionResult, QueueControlAction, QueueItemPriority, QueueItemStatus
from app.modules.queue_control.queue_state_service import QueueStateService


class QueuePriorityService:
    def __init__(self, state_service: QueueStateService | None = None) -> None:
        self.state_service = state_service or QueueStateService()

    def prioritize_items(
        self,
        job_id: str,
        item_ids: list[str],
        priority: QueueItemPriority = QueueItemPriority.high,
    ) -> QueueActionResult:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        affected = 0
        items = []
        for item in state.items:
            if item.id in item_ids and _can_reorder(item.status):
                item = item.model_copy(update={"priority": priority})
                affected += 1
            items.append(item)
        self.state_service.save_queue_state(state.model_copy(update={"items": items}))
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.prioritize_selected,
            affected_items=affected,
            message=f"Đã ưu tiên {affected} item.",
        )

    def move_to_top(self, job_id: str, item_ids: list[str]) -> QueueActionResult:
        return self._move(job_id, item_ids, to_top=True)

    def move_to_bottom(self, job_id: str, item_ids: list[str]) -> QueueActionResult:
        return self._move(job_id, item_ids, to_top=False)

    def reorder_items(self, job_id: str, ordered_item_ids: list[str]) -> QueueActionResult:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        editable = [item for item in state.items if _can_reorder(item.status)]
        locked = [item for item in state.items if not _can_reorder(item.status)]
        by_id = {item.id: item for item in editable}
        ordered = [by_id[item_id] for item_id in ordered_item_ids if item_id in by_id]
        ordered.extend(item for item in editable if item.id not in ordered_item_ids)
        next_items = locked + [item.model_copy(update={"order_index": index}) for index, item in enumerate(ordered, start=len(locked) + 1)]
        self.state_service.save_queue_state(state.model_copy(update={"items": sorted(next_items, key=lambda item: item.order_index)}))
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.move_to_top,
            affected_items=len(ordered),
            message="Đã sắp xếp lại hàng đợi.",
        )

    def _move(self, job_id: str, item_ids: list[str], to_top: bool) -> QueueActionResult:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        movable = [item for item in state.items if item.id in item_ids and _can_reorder(item.status)]
        movable_ids = {item.id for item in movable}
        others = [item for item in state.items if item.id not in movable_ids]
        ordered = movable + others if to_top else others + movable
        ordered = [item.model_copy(update={"order_index": index}) for index, item in enumerate(ordered, start=1)]
        self.state_service.save_queue_state(state.model_copy(update={"items": ordered}))
        action = QueueControlAction.move_to_top if to_top else QueueControlAction.move_to_bottom
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=action,
            affected_items=len(movable),
            message=f"Đã di chuyển {len(movable)} item.",
        )


def _can_reorder(status: QueueItemStatus) -> bool:
    return status not in {QueueItemStatus.completed, QueueItemStatus.rendered, QueueItemStatus.running}
