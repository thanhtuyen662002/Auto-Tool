from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app import database
from app.modules.queue_control.queue_control_schema import QueueItemStatus, QueueState
from app.modules.queue_control.queue_state_service import QueueStateService


class QueueWatchdogService:
    """Detect queue items that have stopped reporting progress for too long."""

    def __init__(self, state_service: QueueStateService | None = None) -> None:
        self.state_service = state_service or QueueStateService()

    def inspect(self, job_id: str, *, mutate: bool = True, now: datetime | None = None) -> dict[str, Any]:
        state = self.state_service.load_queue_state(job_id) or self.state_service.rebuild_from_checkpoints(job_id)
        settings = state.settings
        if not settings.watchdog_enabled:
            return {"stale_items": [], "state": state}

        current_time = now or datetime.now()
        stale_items = _stale_running_items(state, current_time)
        if not stale_items:
            return {"stale_items": [], "state": state}

        messages = [
            _stale_message(item, current_time, settings.watchdog_stale_minutes)
            for item in stale_items
        ]
        new_messages = [message for message in messages if message not in state.warnings]
        updated_state = state
        if mutate and (new_messages or settings.auto_fail_stale_items):
            stale_by_id = {item.id: message for item, message in zip(stale_items, messages, strict=False)}

            def update(current: QueueState) -> QueueState:
                now_text = current_time.replace(microsecond=0).isoformat()
                items = []
                for item in current.items:
                    message = stale_by_id.get(item.id)
                    if not message:
                        items.append(item)
                        continue
                    warnings = _dedupe([*item.warnings, message])
                    if current.settings.auto_fail_stale_items:
                        items.append(
                            item.model_copy(
                                update={
                                    "status": QueueItemStatus.failed,
                                    "current_step": "watchdog_timeout",
                                    "failed_step": "watchdog_timeout",
                                    "error_message": message,
                                    "completed_at": now_text,
                                    "updated_at": now_text,
                                    "warnings": warnings,
                                    "previous_errors": _dedupe([*item.previous_errors, message]),
                                }
                            )
                        )
                    else:
                        items.append(
                            item.model_copy(
                                update={
                                    "current_step": "watchdog_stale",
                                    "updated_at": item.updated_at,
                                    "warnings": warnings,
                                }
                            )
                        )
                return current.model_copy(update={"items": items, "warnings": _dedupe([*current.warnings, *messages])})

            updated_state = self.state_service.update_queue_state(job_id, update)
            for message in new_messages:
                database.add_job_log(job_id, "warning", message)

        return {"stale_items": [item.model_dump(mode="json") for item in stale_items], "messages": messages, "state": updated_state}


def _stale_running_items(state: QueueState, now: datetime) -> list:
    threshold = timedelta(minutes=max(1, int(state.settings.watchdog_stale_minutes)))
    stale = []
    for item in state.items:
        if item.status != QueueItemStatus.running:
            continue
        updated_at = _parse_time(item.updated_at or item.started_at)
        if updated_at is None:
            continue
        if now - updated_at >= threshold:
            stale.append(item)
    return stale


def _stale_message(item, now: datetime, stale_minutes: int) -> str:
    del now
    name = item.filename or item.video_id
    return (
        f"Watchdog: video {name} không có cập nhật trong ít nhất {stale_minutes} phút "
        f"(ngưỡng {stale_minutes} phút). Hãy kiểm tra nhật ký chi tiết của video này."
    )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned
