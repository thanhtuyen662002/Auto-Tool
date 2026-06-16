from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app import database
from app.modules.job_recovery import JobCheckpointService
from app.modules.queue_control.queue_control_schema import (
    QueueItem,
    QueueItemStatus,
    QueueRunStatus,
    QueueSettings,
    QueueState,
)
from app.modules.queue_control.batch_resource_planner import BatchResourcePlanner
from app.modules.queue_control.queue_event_logger import QueueEventLogger
from app.utils.app_paths import app_data_dir


class QueueStateService:
    def __init__(self, storage_root: Path | None = None, event_logger: QueueEventLogger | None = None) -> None:
        self.storage_root = (storage_root or app_data_dir() / "data" / "queue_control").resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.events = event_logger or QueueEventLogger(self.storage_root)

    def create_queue_state(
        self,
        job_id: str,
        mode: str,
        video_paths: list[str],
        settings: QueueSettings,
        output_dir: str,
        project_id: str | None = None,
    ) -> QueueState:
        limited_paths = video_paths[: settings.max_videos_per_batch] if settings.max_videos_per_batch else video_paths
        normalized_settings, concurrency_plan = BatchResourcePlanner().build_plan(
            mode=mode,
            settings=settings,
            output_dir=output_dir,
            total_items=len(limited_paths),
        )
        warnings = list(concurrency_plan.warnings)
        now = _now()
        items = [
            QueueItem(
                id=f"{job_id}:item:{index:03d}",
                job_id=job_id,
                video_id=f"video_{index:03d}",
                video_path=path,
                filename=Path(path).name if path else f"video_{index:03d}",
                order_index=index,
                updated_at=now,
            )
            for index, path in enumerate(limited_paths, start=1)
        ]
        state = QueueState(
            job_id=job_id,
            project_id=project_id,
            mode=_normalize_mode(mode),
            status=QueueRunStatus.running,
            settings=normalized_settings,
            concurrency_plan=concurrency_plan,
            total_items=len(items),
            items=items,
            created_at=now,
            updated_at=now,
            output_dir=str(output_dir),
            warnings=warnings,
        )
        state = self.recalculate_summary(state)
        self.save_queue_state(state)
        self.events.log_event(job_id, "queue_created", {"total_items": state.total_items}, output_dir=str(output_dir))
        return state

    def load_queue_state(self, job_id: str) -> QueueState | None:
        path = self.queue_state_path(job_id)
        if not path.exists():
            return None
        try:
            return QueueState.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError):
            self._quarantine_corrupt_file(path)
            return None

    def save_queue_state(self, state: QueueState) -> QueueState:
        state = self.recalculate_summary(state.model_copy(update={"updated_at": _now()}))
        _atomic_write_json(self.queue_state_path(state.job_id), state.model_dump(mode="json"))
        _atomic_write_json(self.queue_items_path(state.job_id), {"items": [item.model_dump(mode="json") for item in state.items]})
        self._mirror_to_output_dir(state)
        return state

    def update_item_status(
        self,
        job_id: str,
        item_id: str,
        status: QueueItemStatus,
        current_step: str | None = None,
        progress_percent: float | None = None,
        error_message: str | None = None,
        output_video_path: str | None = None,
    ) -> QueueState:
        state = self.load_queue_state(job_id) or self.rebuild_from_checkpoints(job_id)
        now = _now()
        items: list[QueueItem] = []
        for item in state.items:
            if item.id != item_id and item.video_id != item_id:
                items.append(item)
                continue
            update: dict[str, Any] = {
                "status": status,
                "current_step": current_step if current_step is not None else item.current_step,
                "progress_percent": progress_percent if progress_percent is not None else item.progress_percent,
                "updated_at": now,
            }
            if status == QueueItemStatus.running and not item.started_at:
                update["started_at"] = now
            if status in {QueueItemStatus.completed, QueueItemStatus.failed, QueueItemStatus.cancelled, QueueItemStatus.skipped, QueueItemStatus.rendered, QueueItemStatus.needs_review}:
                update["completed_at"] = now
            if error_message is not None:
                update["error_message"] = error_message
            if output_video_path is not None:
                update["output_video_path"] = output_video_path
            items.append(item.model_copy(update=update))
        state = state.model_copy(
            update={
                "items": items,
                "current_item_id": item_id if status == QueueItemStatus.running else state.current_item_id,
                "current_step": current_step if current_step is not None else state.current_step,
            }
        )
        saved = self.save_queue_state(state)
        self.events.log_event(job_id, f"item_{status.value}", {"item_id": item_id, "current_step": current_step}, output_dir=saved.output_dir)
        return saved

    def recalculate_summary(self, state: QueueState) -> QueueState:
        counts = {status: 0 for status in QueueItemStatus}
        for item in state.items:
            counts[item.status] += 1
        done = counts[QueueItemStatus.completed] + counts[QueueItemStatus.rendered] + counts[QueueItemStatus.needs_review]
        total = len(state.items)
        progress = round((done / total) * 100, 2) if total else 0
        return state.model_copy(
            update={
                "total_items": total,
                "queued_items": counts[QueueItemStatus.queued],
                "running_items": counts[QueueItemStatus.running],
                "completed_items": done,
                "failed_items": counts[QueueItemStatus.failed],
                "skipped_items": counts[QueueItemStatus.skipped],
                "cancelled_items": counts[QueueItemStatus.cancelled],
                "needs_review_items": counts[QueueItemStatus.needs_review],
                "progress_percent": progress,
            }
        )

    def rebuild_from_checkpoints(self, job_id: str) -> QueueState:
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Không tìm thấy job: {job_id}")
        outputs = list((job.get("results") or {}).get("outputs") or [])
        total = int(job.get("total_outputs") or len(outputs) or 0)
        now = _now()
        items: list[QueueItem] = []
        for index in range(1, total + 1):
            output = outputs[index - 1] if index - 1 < len(outputs) and isinstance(outputs[index - 1], dict) else {}
            status = _status_from_output(output)
            source = str(output.get("source_video") or output.get("path") or f"video_{index:03d}")
            items.append(
                QueueItem(
                    id=f"{job_id}:item:{index:03d}",
                    job_id=job_id,
                    video_id=f"video_{index:03d}",
                    video_path=source,
                    filename=Path(source).name,
                    order_index=index,
                    status=status,
                    output_video_path=output.get("path") if isinstance(output, dict) else None,
                    failed_step=output.get("failed_step") if isinstance(output, dict) else None,
                    error_message=output.get("error_message") if isinstance(output, dict) else None,
                    updated_at=now,
                )
            )
        checkpoint = JobCheckpointService().load_job_checkpoint(job_id)
        state = QueueState(
            job_id=job_id,
            project_id=job.get("project_id"),
            mode=str(checkpoint.mode) if checkpoint else _mode_from_job(job),
            status=_run_status_from_job(job.get("status")),
            settings=QueueSettings(),
            items=items,
            current_step=job.get("current_step"),
            output_dir=job.get("output_folder"),
            created_at=job.get("created_at") or now,
            updated_at=now,
        )
        return self.save_queue_state(state)

    def queue_state_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "queue_state.json"

    def queue_items_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "queue_items.json"

    def job_dir(self, job_id: str) -> Path:
        return self.storage_root / _safe_name(job_id)

    def _mirror_to_output_dir(self, state: QueueState) -> None:
        if not state.output_dir:
            return
        try:
            out = Path(state.output_dir)
            out.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(out / "queue_state.json", state.model_dump(mode="json"))
            _atomic_write_json(out / "queue_items.json", {"items": [item.model_dump(mode="json") for item in state.items]})
        except OSError:
            return

    def _quarantine_corrupt_file(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            shutil.move(str(path), str(path.with_suffix(path.suffix + f".corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}")))
        except OSError:
            return


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:120] or "job"


def _normalize_mode(mode: str) -> str:
    if mode in {"douyin_reup", "silent_immersive", "subtitle_render", "export_pack", "product_render"}:
        return mode
    if "douyin" in mode:
        return "douyin_reup"
    if "silent" in mode:
        return "silent_immersive"
    if "subtitle" in mode:
        return "subtitle_render"
    if "export" in mode:
        return "export_pack"
    return "product_render"


def _mode_from_job(job: dict[str, Any]) -> str:
    outputs = (job.get("results") or {}).get("outputs") or []
    if any(isinstance(item, dict) and item.get("reup_mode") == "silent_immersive" for item in outputs):
        return "silent_immersive"
    if any(isinstance(item, dict) and item.get("source_video") for item in outputs):
        return "douyin_reup"
    if any(isinstance(item, dict) and item.get("subtitle_review_document_id") for item in outputs):
        return "subtitle_render"
    return "product_render"


def _run_status_from_job(status: str | None) -> QueueRunStatus:
    mapping = {
        "completed_with_errors": QueueRunStatus.completed_with_warnings,
        "interrupted": QueueRunStatus.paused,
        "recoverable": QueueRunStatus.paused,
    }
    if status in mapping:
        return mapping[status]
    try:
        return QueueRunStatus(str(status or "queued"))
    except ValueError:
        return QueueRunStatus.failed


def _status_from_output(output: dict[str, Any]) -> QueueItemStatus:
    status = str(output.get("status") or "queued")
    if status in {"success", "warning"}:
        return QueueItemStatus.completed
    if status == "needs_review":
        return QueueItemStatus.needs_review
    if status == "failed":
        return QueueItemStatus.failed
    if status == "skipped":
        return QueueItemStatus.skipped
    return QueueItemStatus.queued
