from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class OutputReviewStatus(str, Enum):
    pending = "pending"
    good = "good"
    bad = "bad"
    needs_rerender = "needs_rerender"
    ignored = "ignored"


class OutputQualityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(gt=0)
    final_video_path: str
    status: str
    technical_score: float = Field(ge=0, le=1)
    segment_score: float = Field(ge=0, le=1)
    audio_score: float = Field(ge=0, le=1)
    subtitle_score: float = Field(ge=0, le=1)
    timeline_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    recommended_action: str


class OutputReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(gt=0)
    review_status: OutputReviewStatus = OutputReviewStatus.pending
    user_note: str | None = None
    quality_score: OutputQualityScore | None = None
    updated_at: str


class OutputReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_outputs: int
    good: int
    review: int
    needs_rerender: int
    failed: int
    bad: int
    average_overall_score: float
