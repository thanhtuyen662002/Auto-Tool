from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    scan_seconds: float | None = None
    segment_seconds: float | None = None
    scoring_seconds: float | None = None
    timeline_seconds: float | None = None
    script_seconds: float | None = None
    tts_seconds: float | None = None
    subtitle_seconds: float | None = None
    render_visual_seconds: float | None = None
    render_final_seconds: float | None = None
    total_seconds: float | None = None


class PerformanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_runtime_seconds: float = Field(ge=0)
    average_time_per_video: float = Field(ge=0)
    slowest_step: str | None = None
    slowest_output_index: int | None = None

