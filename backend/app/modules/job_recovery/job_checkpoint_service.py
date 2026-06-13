from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from app.modules.job_recovery.job_recovery_schema import (
    JobCheckpoint,
    JobRunStatus,
    JobStepStatus,
    RecoverableStep,
    VideoStepCheckpoint,
)
from app.utils.app_paths import app_data_dir


JobMode = Literal["douyin_reup", "silent_immersive", "subtitle_render", "export_pack", "product_render"]


class JobCheckpointService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or app_data_dir() / "data" / "job_recovery").resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def create_job_checkpoint(
        self,
        job_id: str,
        mode: str,
        project_id: str | None,
        settings_snapshot: dict[str, Any],
        output_dir: str,
    ) -> JobCheckpoint:
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = job_dir / "settings_snapshot.json"
        _atomic_write_json(snapshot_path, settings_snapshot)
        normalized_mode = _normalize_mode(mode)
        checkpoint = JobCheckpoint(
            id=f"checkpoint:{job_id}",
            job_id=job_id,
            project_id=project_id,
            mode=normalized_mode,
            status=JobRunStatus.pending,
            last_checkpoint_at=_now(),
            settings_snapshot_path=str(snapshot_path),
            summary_path=_summary_path(output_dir, normalized_mode),
            job_log_path=str(job_dir / "job_recovery.log"),
        )
        self._save_job_checkpoint(checkpoint)
        self._save_video_checkpoints(job_id, [])
        self._mirror_to_output_dir(job_id, output_dir)
        return checkpoint

    def update_job_status(
        self,
        job_id: str,
        status: JobRunStatus,
        current_step: RecoverableStep | str | None = None,
        current_video_id: str | None = None,
    ) -> JobCheckpoint:
        checkpoint = self.load_job_checkpoint(job_id)
        if checkpoint is None:
            checkpoint = self._create_minimal_checkpoint(job_id)
        step = _normalize_step(current_step)
        checkpoint = checkpoint.model_copy(
            update={
                "status": status,
                "current_step": step,
                "current_video_id": current_video_id or checkpoint.current_video_id,
                "last_safe_step": step if status in {JobRunStatus.completed, JobRunStatus.running} else checkpoint.last_safe_step,
                "last_checkpoint_at": _now(),
            }
        )
        self._save_job_checkpoint(checkpoint)
        return checkpoint

    def update_counts(
        self,
        job_id: str,
        total_items: int | None = None,
        completed_items: int | None = None,
        failed_items: int | None = None,
        interrupted_items: int | None = None,
    ) -> JobCheckpoint:
        checkpoint = self.load_job_checkpoint(job_id) or self._create_minimal_checkpoint(job_id)
        update: dict[str, Any] = {"last_checkpoint_at": _now()}
        if total_items is not None:
            update["total_items"] = max(0, int(total_items))
        if completed_items is not None:
            update["completed_items"] = max(0, int(completed_items))
        if failed_items is not None:
            update["failed_items"] = max(0, int(failed_items))
        if interrupted_items is not None:
            update["interrupted_items"] = max(0, int(interrupted_items))
        checkpoint = checkpoint.model_copy(update=update)
        self._save_job_checkpoint(checkpoint)
        return checkpoint

    def mark_step_started(
        self,
        job_id: str,
        video_id: str,
        video_path: str,
        step: RecoverableStep,
        input_paths: dict[str, str] | None = None,
    ) -> VideoStepCheckpoint:
        checkpoint = VideoStepCheckpoint(
            id=_step_id(job_id, video_id, step),
            job_id=job_id,
            video_id=video_id,
            video_path=video_path,
            step=step,
            status=JobStepStatus.running,
            started_at=_now(),
            input_paths=input_paths or {},
        )
        self._upsert_video_checkpoint(checkpoint)
        self.update_job_status(job_id, JobRunStatus.running, step, video_id)
        return checkpoint

    def mark_step_completed(
        self,
        job_id: str,
        video_id: str,
        step: RecoverableStep,
        output_paths: dict[str, str] | None = None,
    ) -> VideoStepCheckpoint:
        checkpoint = self._find_video_checkpoint(job_id, video_id, step)
        if checkpoint is None:
            checkpoint = VideoStepCheckpoint(
                id=_step_id(job_id, video_id, step),
                job_id=job_id,
                video_id=video_id,
                video_path="",
                step=step,
                status=JobStepStatus.pending,
            )
        checkpoint = checkpoint.model_copy(
            update={
                "status": JobStepStatus.completed,
                "completed_at": _now(),
                "output_paths": {**checkpoint.output_paths, **(output_paths or {})},
            }
        )
        self._upsert_video_checkpoint(checkpoint)
        self.update_job_status(job_id, JobRunStatus.running, step, video_id)
        return checkpoint

    def mark_step_failed(
        self,
        job_id: str,
        video_id: str,
        step: RecoverableStep,
        error_message: str,
    ) -> VideoStepCheckpoint:
        checkpoint = self._find_video_checkpoint(job_id, video_id, step)
        if checkpoint is None:
            checkpoint = VideoStepCheckpoint(
                id=_step_id(job_id, video_id, step),
                job_id=job_id,
                video_id=video_id,
                video_path="",
                step=step,
                status=JobStepStatus.pending,
            )
        checkpoint = checkpoint.model_copy(
            update={
                "status": JobStepStatus.failed,
                "completed_at": _now(),
                "error_message": error_message,
                "failed_step": step.value,
            }
        )
        self._upsert_video_checkpoint(checkpoint)
        self.update_job_status(job_id, JobRunStatus.recoverable, step, video_id)
        return checkpoint

    def load_job_checkpoint(self, job_id: str) -> JobCheckpoint | None:
        path = self.job_checkpoint_path(job_id)
        if not path.exists():
            return None
        try:
            return JobCheckpoint.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError):
            self._quarantine_corrupt_file(path)
            return None

    def load_video_checkpoints(self, job_id: str) -> list[VideoStepCheckpoint]:
        path = self.video_checkpoints_path(job_id)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload.get("items", payload if isinstance(payload, list) else [])
            return [VideoStepCheckpoint.model_validate(item) for item in items]
        except (OSError, json.JSONDecodeError, ValidationError):
            self._quarantine_corrupt_file(path)
            return []

    def job_dir(self, job_id: str) -> Path:
        return self.storage_root / _safe_name(job_id)

    def job_checkpoint_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job_checkpoint.json"

    def video_checkpoints_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "video_checkpoints.json"

    def _create_minimal_checkpoint(self, job_id: str) -> JobCheckpoint:
        checkpoint = JobCheckpoint(
            id=f"checkpoint:{job_id}",
            job_id=job_id,
            mode="product_render",
            status=JobRunStatus.pending,
            last_checkpoint_at=_now(),
        )
        self._save_job_checkpoint(checkpoint)
        if not self.video_checkpoints_path(job_id).exists():
            self._save_video_checkpoints(job_id, [])
        return checkpoint

    def _save_job_checkpoint(self, checkpoint: JobCheckpoint) -> None:
        _atomic_write_json(self.job_checkpoint_path(checkpoint.job_id), checkpoint.model_dump(mode="json"))

    def _save_video_checkpoints(self, job_id: str, items: list[VideoStepCheckpoint]) -> None:
        _atomic_write_json(
            self.video_checkpoints_path(job_id),
            {"items": [item.model_dump(mode="json") for item in items]},
        )

    def _upsert_video_checkpoint(self, checkpoint: VideoStepCheckpoint) -> None:
        items = self.load_video_checkpoints(checkpoint.job_id)
        next_items = [item for item in items if item.id != checkpoint.id]
        next_items.append(checkpoint)
        next_items.sort(key=lambda item: (item.video_id, item.step.value, item.started_at or ""))
        self._save_video_checkpoints(checkpoint.job_id, next_items)

    def _find_video_checkpoint(
        self,
        job_id: str,
        video_id: str,
        step: RecoverableStep,
    ) -> VideoStepCheckpoint | None:
        target_id = _step_id(job_id, video_id, step)
        return next((item for item in self.load_video_checkpoints(job_id) if item.id == target_id), None)

    def _quarantine_corrupt_file(self, path: Path) -> None:
        if not path.exists():
            return
        corrupt_path = path.with_suffix(path.suffix + f".corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        try:
            shutil.move(str(path), str(corrupt_path))
        except OSError:
            pass

    def _mirror_to_output_dir(self, job_id: str, output_dir: str | None) -> None:
        if not output_dir:
            return
        target = Path(output_dir).expanduser()
        try:
            target.mkdir(parents=True, exist_ok=True)
            checkpoint = self.job_checkpoint_path(job_id)
            videos = self.video_checkpoints_path(job_id)
            if checkpoint.exists():
                shutil.copy2(checkpoint, target / "job_checkpoint.json")
            if videos.exists():
                shutil.copy2(videos, target / "video_checkpoints.json")
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


def _normalize_mode(mode: str) -> JobMode:
    if mode in {"douyin_reup", "silent_immersive", "subtitle_render", "export_pack", "product_render"}:
        return mode  # type: ignore[return-value]
    if "silent" in mode:
        return "silent_immersive"
    if "subtitle" in mode:
        return "subtitle_render"
    if "export" in mode:
        return "export_pack"
    if "douyin" in mode:
        return "douyin_reup"
    return "product_render"


def _normalize_step(step: RecoverableStep | str | None) -> RecoverableStep | None:
    if step is None:
        return None
    if isinstance(step, RecoverableStep):
        return step
    value = str(step).lower()
    if "scan" in value:
        return RecoverableStep.scan
    if "subtitle" in value and "review" not in value:
        return RecoverableStep.subtitle_source
    if "review" in value:
        return RecoverableStep.review_document
    if "asr" in value:
        return RecoverableStep.asr
    if "ocr" in value:
        return RecoverableStep.ocr
    if "translat" in value:
        return RecoverableStep.translation
    if "quality" in value or "qa" in value:
        return RecoverableStep.final_qa
    if "caption" in value:
        return RecoverableStep.caption_generation
    if "tag" in value:
        return RecoverableStep.visual_tagging
    if "tts" in value or "voice" in value:
        return RecoverableStep.tts
    if "render" in value or "video" in value:
        return RecoverableStep.render
    if "export" in value:
        return RecoverableStep.export_pack
    return None


def _step_id(job_id: str, video_id: str, step: RecoverableStep) -> str:
    return f"{job_id}:{video_id}:{step.value}"


def _summary_path(output_dir: str | None, mode: str) -> str | None:
    if not output_dir:
        return None
    name = {
        "douyin_reup": "douyin_reup_summary.json",
        "silent_immersive": "silent_reup_job_summary.json",
        "subtitle_render": "subtitle_review_render_summary.json",
        "product_render": "project_summary.json",
        "export_pack": "export_manifest.json",
    }.get(mode, "project_summary.json")
    return str(Path(output_dir) / name)

