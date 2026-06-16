from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class QueueRunStatus(str, Enum):
    queued = "queued"
    running = "running"
    pausing = "pausing"
    paused = "paused"
    resuming = "resuming"
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"


class QueueItemStatus(str, Enum):
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"
    needs_review = "needs_review"
    rendered = "rendered"


class QueueItemPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"


class QueueControlAction(str, Enum):
    pause = "pause"
    resume = "resume"
    cancel = "cancel"
    retry_failed = "retry_failed"
    retry_selected = "retry_selected"
    skip_selected = "skip_selected"
    prioritize_selected = "prioritize_selected"
    move_to_top = "move_to_top"
    move_to_bottom = "move_to_bottom"


class QueueSettings(BaseModel):
    max_concurrent_videos: int = Field(default=1, ge=1, le=2)
    max_videos_per_batch: int | None = Field(default=None, gt=0)
    batch_chunk_size: int = Field(default=50, ge=1, le=500)
    performance_mode: Literal["safe", "balanced", "fast"] = "safe"
    pause_after_current_item: bool = True
    allow_parallel_asr: bool = False
    allow_parallel_ocr: bool = False
    allow_parallel_render: bool = False
    skip_completed_outputs: bool = True
    do_not_overwrite_existing_outputs: bool = True
    stop_batch_on_critical_error: bool = False
    continue_on_video_error: bool = True
    cooldown_seconds_between_renders: int = Field(default=0, ge=0)
    resource_guard_enabled: bool = True
    min_free_disk_gb: float = Field(default=5.0, ge=0)
    max_cpu_percent_warning: float = Field(default=90.0, ge=0, le=100)
    max_memory_percent_warning: float = Field(default=90.0, ge=0, le=100)
    item_timeout_seconds: int = Field(default=1800, ge=60, le=24 * 60 * 60)
    ffmpeg_timeout_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)
    watchdog_enabled: bool = True
    watchdog_stale_minutes: int = Field(default=20, ge=1, le=24 * 60)
    auto_fail_stale_items: bool = False
    pause_on_repeated_failures: bool = True
    max_consecutive_failures: int = Field(default=10, ge=1, le=1000)

    @field_validator("max_concurrent_videos")
    @classmethod
    def force_safe_concurrency(cls, value: int) -> int:
        return max(1, min(value, 2))


class BatchResourcePlan(BaseModel):
    requested_concurrency: int = 1
    effective_concurrency: int = 1
    recommended_concurrency: int = 1
    worker_pool_enabled: bool = False
    execution_mode: Literal["sequential", "parallel_ready", "clamped"] = "sequential"
    mode: str = "product_render"
    total_items: int = 0
    chunk_size: int = 50
    chunk_count: int = 0
    estimated_items_per_hour: float | None = None
    stage_limits: dict[str, int] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class QueueItem(BaseModel):
    id: str
    job_id: str
    video_id: str
    video_path: str
    filename: str | None = None
    status: QueueItemStatus = QueueItemStatus.queued
    priority: QueueItemPriority = QueueItemPriority.normal
    order_index: int
    current_step: str | None = None
    progress_percent: float = 0
    output_video_path: str | None = None
    failed_step: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    warnings: list[str] = Field(default_factory=list)
    previous_errors: list[str] = Field(default_factory=list)


class QueueState(BaseModel):
    job_id: str
    project_id: str | None = None
    mode: Literal["douyin_reup", "silent_immersive", "subtitle_render", "export_pack", "product_render"] = "product_render"
    status: QueueRunStatus
    settings: QueueSettings
    concurrency_plan: BatchResourcePlan | None = None
    total_items: int = 0
    queued_items: int = 0
    running_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    cancelled_items: int = 0
    needs_review_items: int = 0
    progress_percent: float = 0
    current_item_id: str | None = None
    current_step: str | None = None
    items: list[QueueItem] = Field(default_factory=list)
    pause_requested: bool = False
    cancel_requested: bool = False
    created_at: str
    updated_at: str
    output_dir: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class QueueActionRequest(BaseModel):
    action: QueueControlAction | None = None
    item_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


class QueueActionResult(BaseModel):
    success: bool
    job_id: str
    action: QueueControlAction
    affected_items: int = 0
    message: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class QueueStateResponse(BaseModel):
    success: bool
    data: QueueState
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResourceStatusResponse(BaseModel):
    success: bool
    data: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
