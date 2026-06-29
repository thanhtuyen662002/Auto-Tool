from __future__ import annotations

from datetime import datetime
from typing import Any

from app import database
from app.modules.job_recovery.job_checkpoint_service import JobCheckpointService
from app.modules.job_recovery.job_recovery_schema import JobRunStatus, RecoveryCandidate
from app.modules.queue_control.queue_state_service import QueueStateService


RECOVERABLE_DB_STATUSES = {"queued", "running", "processing", "interrupted", "recoverable"}


class JobRecoveryService:
    def __init__(self, checkpoint_service: JobCheckpointService | None = None) -> None:
        self.checkpoints = checkpoint_service or JobCheckpointService()
        self.queue_states = QueueStateService()

    def find_recovery_candidates(self) -> list[RecoveryCandidate]:
        return [self._candidate_from_job(job) for job in self._list_candidate_jobs()]

    def inspect_job_recovery(self, job_id: str) -> RecoveryCandidate:
        job = database.get_job(job_id)
        if not job:
            raise LookupError(f"Không tìm thấy job: {job_id}")
        return self._candidate_from_job(job)

    def mark_interrupted_jobs_on_startup(self) -> list[RecoveryCandidate]:
        marked: list[RecoveryCandidate] = []
        for job in self._list_jobs_by_status({"running", "processing", "queued"}):
            status = "recoverable" if int(job.get("completed_outputs") or 0) > 0 else "interrupted"
            database.update_job(job["job_id"], status=status, current_step=job.get("current_step") or "interrupted")
            database.add_job_log(
                job["job_id"],
                "warning",
                "Job bị gián đoạn ở lần chạy trước. Hãy mở Recovery Center để kiểm tra hoặc resume.",
            )
            self.checkpoints.update_job_status(
                job["job_id"],
                JobRunStatus.recoverable if status == "recoverable" else JobRunStatus.interrupted,
                job.get("current_step"),
            )
            marked.append(self.inspect_job_recovery(job["job_id"]))
        return marked

    def count_recoverable_jobs(self) -> int:
        return len(self.find_recovery_candidates())

    def mark_cancelled(self, job_id: str) -> RecoveryCandidate:
        if not database.get_job(job_id):
            raise LookupError(f"Không tìm thấy job: {job_id}")
        database.update_job(job_id, status="cancelled", current_step="cancelled", progress=100)
        database.add_job_log(job_id, "warning", "Người dùng đã đánh dấu job là đã hủy trong Recovery Center.")
        self.checkpoints.update_job_status(job_id, JobRunStatus.cancelled, None)
        return self.inspect_job_recovery(job_id)

    def _list_candidate_jobs(self) -> list[dict[str, Any]]:
        return self._list_jobs_by_status(RECOVERABLE_DB_STATUSES | {"failed", "completed_with_errors"})

    def _list_jobs_by_status(self, statuses: set[str]) -> list[dict[str, Any]]:
        with database.get_connection() as conn:
            placeholders = ",".join("?" for _ in statuses)
            rows = conn.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY updated_at DESC",
                tuple(statuses),
            ).fetchall()
        jobs = []
        for row in rows:
            job = database._row_to_job(row)  # type: ignore[attr-defined]
            if _is_recovery_relevant(job):
                jobs.append(job)
        return jobs

    def _candidate_from_job(self, job: dict[str, Any]) -> RecoveryCandidate:
        project = database.get_project(job["project_id"]) if job.get("project_id") else None
        checkpoint = self.checkpoints.load_job_checkpoint(job["job_id"])
        completed = int(job.get("completed_outputs") or 0)
        failed = int(job.get("failed_outputs") or 0)
        total = int(job.get("total_outputs") or 0)
        skipped = 0
        cancelled = 0
        queue_state = self.queue_states.load_queue_state(job["job_id"])
        if queue_state and queue_state.total_items:
            total = int(queue_state.total_items or len(queue_state.items) or total)
            completed = int(queue_state.completed_items or 0)
            failed = int(queue_state.failed_items or 0)
            skipped = int(queue_state.skipped_items or 0)
            cancelled = int(queue_state.cancelled_items or 0)
        interrupted = max(0, total - completed - failed - skipped - cancelled) if job.get("status") not in {"completed", "completed_with_errors"} else 0
        status = _normalize_run_status(job.get("status"))
        mode = str(checkpoint.mode) if checkpoint else _infer_mode(job)
        return RecoveryCandidate(
            job_id=job["job_id"],
            project_id=job.get("project_id"),
            mode=mode,
            status=status,
            project_name=_project_name(project),
            started_at=job.get("created_at"),
            last_checkpoint_at=(checkpoint.last_checkpoint_at if checkpoint else job.get("updated_at")),
            total_items=total,
            completed_items=completed,
            failed_items=failed,
            interrupted_items=interrupted,
            recoverable=status in {JobRunStatus.interrupted, JobRunStatus.recoverable, JobRunStatus.failed}
            or interrupted > 0
            or failed > 0,
            recommended_action=_recommended_action(completed, failed, interrupted, status),
            reason=_reason(completed, failed, interrupted, status, job.get("current_step")),
            summary_path=(checkpoint.summary_path if checkpoint else _summary_from_job(job)),
            warnings=[],
        )


def _normalize_run_status(status: str | None) -> JobRunStatus:
    value = str(status or "pending")
    if value == "completed_with_errors":
        return JobRunStatus.completed_with_warnings
    try:
        return JobRunStatus(value)
    except ValueError:
        return JobRunStatus.recoverable if value in RECOVERABLE_DB_STATUSES else JobRunStatus.failed


def _recommended_action(completed: int, failed: int, interrupted: int, status: JobRunStatus) -> str:
    if interrupted > 0 or status in {JobRunStatus.interrupted, JobRunStatus.recoverable}:
        return "resume"
    if failed > 0:
        return "retry_failed"
    if completed > 0:
        return "open_results"
    return "inspect"


def _reason(completed: int, failed: int, interrupted: int, status: JobRunStatus, step: str | None) -> str:
    if interrupted > 0:
        return f"Job bị gián đoạn ở bước {step or 'không rõ'}, còn {interrupted} mục chưa hoàn tất."
    if failed > 0:
        return f"Job có {failed} mục lỗi, có thể retry các mục failed."
    if completed > 0:
        return "Job có kết quả tạm thời có thể mở để kiểm tra."
    return f"Job ở trạng thái {status.value}, nên inspect trước khi xử lý tiếp."


def _project_name(project: dict[str, Any] | None) -> str | None:
    if not project:
        return None
    return str((project.get("config") or {}).get("project_name") or project.get("project_id"))


def _infer_mode(job: dict[str, Any]) -> str:
    results = job.get("results") or {}
    outputs = results.get("outputs") or []
    if any(isinstance(item, dict) and item.get("reup_mode") == "silent_immersive" for item in outputs):
        return "silent_immersive"
    if any(isinstance(item, dict) and item.get("source_video") for item in outputs):
        return "douyin_reup"
    if any(isinstance(item, dict) and item.get("subtitle_review_document_id") for item in outputs):
        return "subtitle_render"
    
    project_id = job.get("project_id")
    if project_id:
        project = database.get_project(project_id)
        if project and project.get("config"):
            cfg = project["config"]
            if cfg.get("douyin_reup", {}).get("enabled", False):
                if cfg.get("enable_silent_immersive_mode", False):
                    return "silent_immersive"
                return "douyin_reup"
                
    return "product_render"


def _summary_from_job(job: dict[str, Any]) -> str | None:
    summary = (job.get("results") or {}).get("summary") or {}
    if isinstance(summary, dict):
        return summary.get("summary_file") or summary.get("summary_path")
    folder = job.get("output_folder")
    return str(folder) if folder else None


def _is_recovery_relevant(job: dict[str, Any]) -> bool:
    if job.get("status") in RECOVERABLE_DB_STATUSES:
        return True
    if job.get("status") in {"failed", "completed_with_errors"}:
        return int(job.get("failed_outputs") or 0) > 0 or int(job.get("completed_outputs") or 0) > 0
    return False
