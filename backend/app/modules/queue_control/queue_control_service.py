from __future__ import annotations

from app import database
from app.modules.queue_control.queue_control_schema import (
    QueueActionRequest,
    QueueActionResult,
    QueueControlAction,
    QueueItemStatus,
    QueueRunStatus,
)
from app.modules.queue_control.queue_event_logger import QueueEventLogger
from app.modules.queue_control.queue_state_service import QueueStateService


class QueueControlService:
    def __init__(self, state_service: QueueStateService | None = None, event_logger: QueueEventLogger | None = None) -> None:
        self.state_service = state_service or QueueStateService()
        self.events = event_logger or QueueEventLogger()

    def request_pause(self, job_id: str) -> QueueActionResult:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        finished = {
            QueueRunStatus.completed,
            QueueRunStatus.completed_with_warnings,
            QueueRunStatus.failed,
            QueueRunStatus.cancelled,
        }
        if state.status in finished:
            return QueueActionResult(
                success=False,
                job_id=job_id,
                action=QueueControlAction.pause,
                message="Job đã kết thúc, không thể tạm dừng.",
            )
        state = self.state_service.update_queue_state(
            job_id,
            lambda current: current.model_copy(update={"status": QueueRunStatus.pausing, "pause_requested": True}),
        )
        database.update_job(job_id, status="pausing", current_step=state.current_step or "pausing")
        database.add_job_log(job_id, "warning", "Người dùng yêu cầu tạm dừng. Job sẽ dừng sau item hiện tại.")
        self.events.log_event(job_id, "pause_requested", output_dir=state.output_dir)
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.pause,
            message="Job sẽ tạm dừng sau video hiện tại.",
        )

    def resume(self, job_id: str) -> QueueActionResult:
        state = self.state_service.update_queue_state(
            job_id,
            lambda current: current.model_copy(update={"status": QueueRunStatus.resuming, "pause_requested": False, "cancel_requested": False}),
        )
        database.update_job(job_id, status="resuming", current_step="resuming")
        database.add_job_log(job_id, "info", "Người dùng yêu cầu tiếp tục job.")
        self.events.log_event(job_id, "resume_requested", output_dir=state.output_dir)
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.resume,
            message="Job đã chuyển sang trạng thái tiếp tục.",
        )

    def request_cancel(self, job_id: str) -> QueueActionResult:
        state = self.state_service.update_queue_state(
            job_id,
            lambda current: current.model_copy(update={"status": QueueRunStatus.cancel_requested, "cancel_requested": True}),
        )
        database.update_job(job_id, status="cancel_requested", current_step=state.current_step or "cancel_requested")
        database.add_job_log(job_id, "warning", "Người dùng yêu cầu hủy batch. Output đã xong sẽ được giữ lại.")
        self.events.log_event(job_id, "cancel_requested", output_dir=state.output_dir)
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.cancel,
            message="Job sẽ hủy an toàn trước item tiếp theo.",
        )

    def skip_items(self, job_id: str, item_ids: list[str]) -> QueueActionResult:
        skipped = 0

        def mutate(current):
            nonlocal skipped
            items = []
            for item in current.items:
                if item.id in item_ids and item.status not in {QueueItemStatus.completed, QueueItemStatus.rendered, QueueItemStatus.running}:
                    item = item.model_copy(update={"status": QueueItemStatus.skipped, "progress_percent": 100})
                    skipped += 1
                items.append(item)
            return current.model_copy(update={"items": items})

        state = self.state_service.update_queue_state(job_id, mutate)
        self.events.log_event(job_id, "items_skipped", {"item_ids": item_ids, "affected": skipped}, output_dir=state.output_dir)
        return QueueActionResult(
            success=True,
            job_id=job_id,
            action=QueueControlAction.skip_selected,
            affected_items=skipped,
            message=f"Đã bỏ qua {skipped} item.",
        )

    def apply_action(self, job_id: str, request: QueueActionRequest) -> QueueActionResult:
        if request.action is None:
            return QueueActionResult(
                success=False,
                job_id=job_id,
                action=QueueControlAction.pause,
                message="Thiếu action cho yêu cầu queue control.",
            )
        if request.action == QueueControlAction.pause:
            return self.request_pause(job_id)
        if request.action == QueueControlAction.resume:
            return self.resume(job_id)
        if request.action == QueueControlAction.cancel:
            return self.request_cancel(job_id)
        if request.action == QueueControlAction.skip_selected:
            return self.skip_items(job_id, request.item_ids)
        return QueueActionResult(
            success=False,
            job_id=job_id,
            action=request.action,
            message="Action cần service chuyên biệt.",
        )

    def should_pause(self, job_id: str) -> bool:
        state = self.state_service.load_queue_state(job_id)
        if not state:
            return False
        return state.pause_requested or state.status == QueueRunStatus.pausing

    def should_cancel(self, job_id: str) -> bool:
        state = self.state_service.load_queue_state(job_id)
        if not state:
            job = database.get_job(job_id)
            return bool(job and job.get("status") == "cancel_requested")
        return state.cancel_requested or state.status == QueueRunStatus.cancel_requested

    def mark_paused(self, job_id: str, reason: str = "Job đã tạm dừng sau item hiện tại.") -> None:
        state = self.state_service.update_queue_state(
            job_id,
            lambda current: current.model_copy(update={"status": QueueRunStatus.paused, "pause_requested": True}),
        )
        database.update_job(job_id, status="paused", current_step="paused")
        database.add_job_log(job_id, "warning", reason)
        self.events.log_event(job_id, "job_paused", {"reason": reason}, output_dir=state.output_dir)

    def mark_cancelled(self, job_id: str, reason: str = "Job đã hủy theo yêu cầu người dùng.") -> None:
        def mutate(current):
            items = [
                item.model_copy(update={"status": QueueItemStatus.cancelled})
                if item.status in {QueueItemStatus.queued, QueueItemStatus.paused}
                else item
                for item in current.items
            ]
            return current.model_copy(update={"status": QueueRunStatus.cancelled, "cancel_requested": True, "items": items})

        state = self.state_service.update_queue_state(job_id, mutate)
        database.update_job(job_id, status="cancelled", current_step="cancelled", progress=100)
        database.add_job_log(job_id, "warning", reason)
        self.events.log_event(job_id, "job_cancelled", {"reason": reason}, output_dir=state.output_dir)
