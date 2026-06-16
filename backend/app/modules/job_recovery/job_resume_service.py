from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.modules.job_recovery.job_checkpoint_service import JobCheckpointService
from app.modules.job_recovery.job_lock_service import JobLockService
from app.modules.job_recovery.job_reconciliation_service import JobReconciliationService
from app.modules.job_recovery.job_recovery_schema import ResumeJobRequest, ResumeJobResult
from app.modules.queue_control.queue_control_schema import QueueItemStatus
from app.modules.queue_control.queue_state_service import QueueStateService
from app.utils.app_paths import app_data_dir


class JobResumeService:
    def __init__(
        self,
        reconciliation_service: JobReconciliationService | None = None,
        checkpoint_service: JobCheckpointService | None = None,
        lock_service: JobLockService | None = None,
    ) -> None:
        self.reconciliation = reconciliation_service or JobReconciliationService()
        self.checkpoints = checkpoint_service or JobCheckpointService()
        self.locks = lock_service or JobLockService()

    def resume_job(self, request: ResumeJobRequest) -> ResumeJobResult:
        if not request.job_id:
            return ResumeJobResult(success=False, original_job_id="", errors=["Thiếu job_id để resume."])
        if not self.locks.acquire_job_lock(request.job_id):
            return ResumeJobResult(
                success=False,
                original_job_id=request.job_id,
                errors=["Job đang có lock resume khác. Hãy đợi job hiện tại xong hoặc cleanup lock nếu chắc chắn đã stale."],
            )
        try:
            plan = self.build_resume_plan(request.job_id, request)
            new_job_id = self.create_resume_job(request.job_id, plan) if plan["resumed_items"] or plan["retry_items"] else None
            manifest_path = self._write_resume_manifest(request.job_id, new_job_id, request, plan)
            log_path = self._write_resume_log(request.job_id, new_job_id, plan)
            return ResumeJobResult(
                success=True,
                new_job_id=new_job_id,
                original_job_id=request.job_id,
                resumed_items=int(plan["resumed_items"]),
                skipped_completed_items=int(plan["skipped_completed_items"]),
                retry_items=int(plan["retry_items"]),
                warnings=list(plan.get("warnings") or []),
                errors=[],
                resume_manifest_path=str(manifest_path),
                resume_log_path=str(log_path),
                resume_plan=plan,
            )
        except Exception as exc:
            self.locks.release_job_lock(request.job_id)
            return ResumeJobResult(success=False, original_job_id=request.job_id, errors=[str(exc)])

    def build_resume_plan(self, job_id: str, request: ResumeJobRequest) -> dict[str, Any]:
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Không tìm thấy job: {job_id}")
        reconciliation = self.reconciliation.reconcile_job_outputs(job_id)
        outputs = reconciliation.get("outputs") or []
        skipped = [
            item
            for item in outputs
            if isinstance(item, dict)
            and item.get("reconciled_output_exists")
            and request.skip_completed_outputs
        ]
        failed = [item for item in outputs if isinstance(item, dict) and item.get("recovery_status") == "failed"]
        interrupted = [item for item in outputs if isinstance(item, dict) and item.get("recovery_status") == "interrupted"]
        pending_count = max(0, int(job.get("total_outputs") or 0) - len(outputs))
        queue_retry_items, queue_resume_items = _queue_resume_items(job_id, request.resume_mode)
        synthetic_pending = [] if queue_resume_items else _pending_items(job_id, pending_count)
        if request.resume_mode == "retry_failed":
            retry_items = _merge_resume_items(failed, queue_retry_items)
            resume_items = []
        elif request.resume_mode == "retry_interrupted":
            retry_items = _merge_resume_items(interrupted, queue_retry_items)
            resume_items = []
        elif request.resume_mode == "continue_pending":
            retry_items = []
            resume_items = _merge_resume_items(interrupted + synthetic_pending, queue_resume_items)
        else:
            retry_items = _merge_resume_items(interrupted, queue_retry_items)
            resume_items = _merge_resume_items(synthetic_pending, queue_resume_items)
        if request.max_items is not None:
            limit = max(0, request.max_items)
            retry_items = retry_items[:limit]
            remaining = max(0, limit - len(retry_items))
            resume_items = resume_items[:remaining]
        warnings = []
        if request.do_not_overwrite_existing_outputs and skipped:
            warnings.append("Các output đã tồn tại sẽ được bỏ qua, không ghi đè.")
        return {
            "original_job_id": job_id,
            "project_id": job.get("project_id"),
            "resume_mode": request.resume_mode,
            "skip_completed_outputs": request.skip_completed_outputs,
            "do_not_overwrite_existing_outputs": request.do_not_overwrite_existing_outputs,
            "skipped_completed_items": len(skipped),
            "retry_items": len(retry_items),
            "resumed_items": len(retry_items) + len(resume_items),
            "retry_outputs": retry_items,
            "pending_outputs": resume_items,
            "selected_source_videos": _source_videos_from_resume_items([*retry_items, *resume_items]),
            "warnings": warnings,
            "reconciliation": reconciliation,
        }

    def create_resume_job(self, original_job_id: str, resume_plan: dict[str, Any]) -> str:
        original_job = database.get_job(original_job_id)
        if not original_job:
            raise LookupError(f"Không tìm thấy job: {original_job_id}")
        new_job_id = str(uuid.uuid4())
        total = max(1, int(resume_plan.get("resumed_items") or resume_plan.get("retry_items") or 1))
        database.create_job(new_job_id, original_job["project_id"], preview_only=False, total_outputs=total)
        database.update_job(new_job_id, current_step="resume_queued")
        database.add_job_log(new_job_id, "info", f"Job resume được tạo từ job gốc {original_job_id}.")
        project = database.get_project(original_job["project_id"])
        settings_snapshot = (project or {}).get("config") or {}
        checkpoint = self.checkpoints.create_job_checkpoint(
            new_job_id,
            _mode_from_plan_or_job(resume_plan, original_job),
            original_job["project_id"],
            settings_snapshot,
            str(_resume_dir(original_job_id)),
        )
        self.checkpoints.update_counts(new_job_id, total_items=total)
        return checkpoint.job_id

    def release_resume_lock(self, original_job_id: str) -> None:
        self.locks.release_job_lock(original_job_id)

    def _write_resume_manifest(
        self,
        original_job_id: str,
        new_job_id: str | None,
        request: ResumeJobRequest,
        plan: dict[str, Any],
    ) -> Path:
        path = _resume_dir(original_job_id) / "resume_manifest.json"
        payload = {
            "original_job_id": original_job_id,
            "resume_job_id": new_job_id,
            "resume_mode": request.resume_mode,
            "skipped_completed_items": plan.get("skipped_completed_items", 0),
            "resumed_items": plan.get("resumed_items", 0),
            "retry_items": plan.get("retry_items", 0),
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
            "plan": plan,
        }
        _write_json(path, payload)
        return path

    def _write_resume_log(self, original_job_id: str, new_job_id: str | None, plan: dict[str, Any]) -> Path:
        path = _resume_dir(original_job_id) / "resume_log.json"
        _write_json(
            path,
            {
                "original_job_id": original_job_id,
                "resume_job_id": new_job_id,
                "created_at": datetime.now().replace(microsecond=0).isoformat(),
                "status": "created",
                "warnings": plan.get("warnings", []),
            },
        )
        return path


def _pending_items(job_id: str, count: int) -> list[dict[str, Any]]:
    return [{"index": index + 1, "status": "pending", "source_video": "", "recovery_status": "pending", "job_id": job_id} for index in range(max(0, count))]


def _queue_resume_items(job_id: str, resume_mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    state = QueueStateService().load_queue_state(job_id)
    if state is None:
        return [], []
    retry_items: list[dict[str, Any]] = []
    resume_items: list[dict[str, Any]] = []
    for item in sorted(state.items, key=lambda value: value.order_index):
        payload = {
            "index": item.order_index,
            "status": item.status.value,
            "source_video": item.video_path,
            "recovery_status": item.status.value,
            "job_id": job_id,
            "queue_item_id": item.id,
        }
        if resume_mode == "retry_failed" and item.status == QueueItemStatus.failed:
            retry_items.append(payload)
        elif resume_mode == "retry_interrupted" and item.status in {QueueItemStatus.running, QueueItemStatus.paused, QueueItemStatus.cancelled}:
            retry_items.append(payload)
        elif resume_mode == "continue_pending" and item.status in {QueueItemStatus.queued, QueueItemStatus.running, QueueItemStatus.paused}:
            resume_items.append(payload)
        elif resume_mode == "reconcile_then_continue":
            if item.status in {QueueItemStatus.running, QueueItemStatus.paused, QueueItemStatus.cancelled}:
                retry_items.append(payload)
            elif item.status == QueueItemStatus.queued:
                resume_items.append(payload)
    return retry_items, resume_items


def _merge_resume_items(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*secondary, *primary]:
        key = str(item.get("source_video") or item.get("index") or len(merged)).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return sorted(merged, key=lambda item: int(item.get("index") or 0))


def _source_videos_from_resume_items(items: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for item in items:
        path = str(item.get("source_video") or "").strip()
        if not path:
            continue
        key = str(Path(path).expanduser().resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def _resume_dir(original_job_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in original_job_id)[:120] or "job"
    path = app_data_dir() / "data" / "job_recovery" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _mode_from_plan_or_job(plan: dict[str, Any], job: dict[str, Any]) -> str:
    outputs = (job.get("results") or {}).get("outputs") or []
    if any(isinstance(item, dict) and item.get("reup_mode") == "silent_immersive" for item in outputs):
        return "silent_immersive"
    if any(isinstance(item, dict) and item.get("source_video") for item in outputs):
        return "douyin_reup"
    if any(isinstance(item, dict) and item.get("subtitle_review_document_id") for item in outputs):
        return "subtitle_render"
    return "product_render"
