from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SegmentScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    source_path: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    duration: float = Field(gt=0)
    brightness_score: float = Field(ge=0, le=1)
    sharpness_score: float = Field(ge=0, le=1)
    motion_score: float = Field(ge=0, le=1)
    freeze_score: float = Field(ge=0, le=1)
    stability_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    is_rejected: bool
    reject_reasons: list[str]
    tags: list[str] = Field(default_factory=list)
    cache_hit: bool = False
