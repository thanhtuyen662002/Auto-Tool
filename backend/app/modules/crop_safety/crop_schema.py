from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SafeZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: float
    height: float
    label: str


class CropBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CropAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    start: float | None = None
    end: float | None = None

    input_width: int = Field(gt=0)
    input_height: int = Field(gt=0)
    target_width: int = Field(gt=0)
    target_height: int = Field(gt=0)

    recommended_crop: CropBox
    crop_mode: str

    visibility_score: float = Field(ge=0, le=1)
    overlay_risk_score: float = Field(ge=0, le=1)
    edge_risk_score: float = Field(ge=0, le=1)
    zoom_risk_score: float = Field(ge=0, le=1)
    overall_safety_score: float = Field(ge=0, le=1)

    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    effective_zoom_motion: int | None = None
    cache_hit: bool = False


class CropSafetyClipReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(gt=0)
    clip_index: int = Field(gt=0)
    source_path: str
    start: float
    end: float
    crop_mode: str
    visibility_score: float
    overlay_risk_score: float
    edge_risk_score: float
    zoom_risk_score: float
    overall_safety_score: float
    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    cache_hit: bool = False


class CropSafetyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    total_clips_analyzed: int
    average_crop_safety_score: float
    fallback_to_blur_background: int
    center_crop_used: int
    warnings_summary: dict[str, int] = Field(default_factory=dict)
    clips: list[CropSafetyClipReport] = Field(default_factory=list)
