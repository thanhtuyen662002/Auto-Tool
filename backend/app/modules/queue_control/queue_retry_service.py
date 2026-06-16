from __future__ import annotations

from app.modules.queue_control.queue_control_schema import QueueActionResult, QueueControlAction, QueueItem, QueueItemStatus
from app.modules.queue_control.queue_state_service import QueueStateService


class QueueRetryService:
    def __init__(self, state_service: QueueStateService | None = None) -> None:
        self.state_service = state_service or QueueStateService()

    def retry_failed_items(self, job_id: str) -> QueueActionResult:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        ids = [item.id for item in state.items if item.status == QueueItemStatus.failed]
        return self.retry_selected_items(job_id, ids, action=QueueControlAction.retry_failed)

    def retry_selected_items(
        self,
        job_id: str,
        item_ids: list[str],
        action: QueueControlAction = QueueControlAction.retry_selected,
    ) -> QueueActionResult:
        affected = 0

        def mutate(state):
            nonlocal affected
            items: list[QueueItem] = []
            for item in state.items:
                if item.id in item_ids and item.status in {QueueItemStatus.failed, QueueItemStatus.cancelled, QueueItemStatus.skipped, QueueItemStatus.paused}:
                    item = self.reset_item_for_retry(item)
                    affected += 1
                items.append(item)
            return state.model_copy(update={"items": items})

        self.state_service.update_queue_state(job_id, mutate)
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=action,
            affected_items=affected,
            message=f"Đã đưa {affected} item về hàng đợi retry.",
        )

    def reset_item_for_retry(self, item: QueueItem) -> QueueItem:
        history = list(item.previous_errors)
        if item.error_message:
            history.append(item.error_message)
        return item.model_copy(
            update={
                "status": QueueItemStatus.queued,
                "progress_percent": 0,
                "current_step": None,
                "error_message": None,
                "previous_errors": history,
                "started_at": None,
                "completed_at": None,
            }
        )
