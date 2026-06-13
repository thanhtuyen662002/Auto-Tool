from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class JobRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    interrupted = "interrupted"
    recoverable = "recoverable"
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    cancelled = "cancelled"


class JobStepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    interrupted = "interrupted"


class RecoverableStep(str, Enum):
    scan = "scan"
    subtitle_source = "subtitle_source"
    asr = "asr"
    ocr = "ocr"
    translation = "translation"
    quality_check = "quality_check"
    review_document = "review_document"
    caption_generation = "caption_generation"
    visual_tagging = "visual_tagging"
    tts = "tts"
    render = "render"
    final_qa = "final_qa"
    export_pack = "export_pack"


class JobCheckpoint(BaseModel):
    id: str
    job_id: str
    project_id: str | None = None
    mode: Literal["douyin_reup", "silent_immersive", "subtitle_render", "export_pack", "product_render"] = "product_render"
    status: JobRunStatus
    current_video_id: str | None = None
    current_video_path: str | None = None
    current_step: RecoverableStep | None = None
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    interrupted_items: int = 0
    last_safe_step: RecoverableStep | None = None
    last_checkpoint_at: str
    settings_snapshot_path: str | None = None
    summary_path: str | None = None
    job_log_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class VideoStepCheckpoint(BaseModel):
    id: str
    job_id: str
    video_id: str
    video_path: str
    step: RecoverableStep
    status: JobStepStatus
    started_at: str | None = None
    completed_at: str | None = None
    input_paths: dict[str, str] = Field(default_factory=dict)
    output_paths: dict[str, str] = Field(default_factory=dict)
    can_resume_from_here: bool = True
    can_skip_if_output_exists: bool = True
    error_message: str | None = None
    failed_step: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RecoveryCandidate(BaseModel):
    job_id: str
    project_id: str | None = None
    mode: str
    status: JobRunStatus
    project_name: str | None = None
    started_at: str | None = None
    last_checkpoint_at: str | None = None
    total_items: int
    completed_items: int
    failed_items: int
    interrupted_items: int
    recoverable: bool
    recommended_action: Literal["resume", "retry_failed", "open_results", "mark_cancelled", "inspect"]
    reason: str
    summary_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ResumeJobRequest(BaseModel):
    job_id: str | None = None
    resume_mode: Literal["continue_pending", "retry_failed", "retry_interrupted", "reconcile_then_continue"] = "reconcile_then_continue"
    skip_completed_outputs: bool = True
    do_not_overwrite_existing_outputs: bool = True
    max_items: int | None = None


class ResumeJobResult(BaseModel):
    success: bool
    new_job_id: str | None = None
    original_job_id: str
    resumed_items: int = 0
    skipped_completed_items: int = 0
    retry_items: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    resume_manifest_path: str | None = None
    resume_log_path: str | None = None
    resume_plan: dict[str, Any] = Field(default_factory=dict)


class JobRecoveryCandidatesData(BaseModel):
    items: list[RecoveryCandidate] = Field(default_factory=list)


class JobRecoveryCandidatesResponse(BaseModel):
    success: bool
    data: JobRecoveryCandidatesData
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class JobRecoveryJobData(BaseModel):
    candidate: RecoveryCandidate
    checkpoint: JobCheckpoint | None = None
    video_checkpoints: list[VideoStepCheckpoint] = Field(default_factory=list)
    reconciliation: dict[str, Any] | None = None
    job: dict[str, Any] | None = None


class JobRecoveryJobResponse(BaseModel):
    success: bool
    data: JobRecoveryJobData
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class JobRecoveryActionResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

