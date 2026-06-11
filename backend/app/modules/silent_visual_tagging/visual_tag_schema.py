from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VisualTagCategory(str, Enum):
    industry = "industry"
    scene = "scene"
    action = "action"
    product_stage = "product_stage"
    quality = "quality"


VisualTagSource = Literal[
    "product_context",
    "ocr_text",
    "folder_name",
    "filename",
    "segment_type",
    "visual_rule",
    "user",
]


INDUSTRY_TAGS = [
    "home_goods",
    "kitchen_goods",
    "desk_setup",
    "storage_organization",
    "beauty_goods",
    "cleaning_goods",
    "dorm_goods",
    "general_product",
]
SCENE_TAGS = [
    "home_scene",
    "kitchen_scene",
    "bathroom_scene",
    "bedroom_scene",
    "desk_scene",
    "dorm_scene",
    "vanity_scene",
    "storage_scene",
    "cleaning_scene",
]
ACTION_TAGS = [
    "unboxing",
    "opening_package",
    "hands_operation",
    "placing_product",
    "assembling",
    "testing",
    "pouring",
    "wiping",
    "cleaning",
    "organizing",
    "folding",
    "comparison",
    "before_after",
    "closeup",
    "product_reveal",
    "usage_demo",
    "result_showcase",
]
PRODUCT_STAGE_TAGS = [
    "packaging",
    "first_look",
    "detail_closeup",
    "demo_step",
    "benefit_scene",
    "final_result",
    "cta_scene",
]
QUALITY_TAGS = [
    "clear_frame",
    "dark_frame",
    "high_motion",
    "low_motion",
    "stable_shot",
    "blur_risk",
]

VISUAL_TAG_VOCABULARY: dict[str, list[str]] = {
    VisualTagCategory.industry.value: INDUSTRY_TAGS,
    VisualTagCategory.scene.value: SCENE_TAGS,
    VisualTagCategory.action.value: ACTION_TAGS,
    VisualTagCategory.product_stage.value: PRODUCT_STAGE_TAGS,
    VisualTagCategory.quality.value: QUALITY_TAGS,
}

TAG_CATEGORY_BY_NAME = {
    tag: VisualTagCategory(category)
    for category, tags in VISUAL_TAG_VOCABULARY.items()
    for tag in tags
}


class VisualTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str
    category: VisualTagCategory
    confidence: float = Field(ge=0, le=1)
    source: VisualTagSource
    reason: str | None = None


class SegmentVisualTagResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    video_path: str
    start: float
    end: float
    tags: list[VisualTag] = Field(default_factory=list)
    primary_industry: str | None = None
    primary_scene: str | None = None
    primary_action: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class VideoVisualTagReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    project_id: str | None = None
    job_id: str | None = None
    segment_results: list[SegmentVisualTagResult] = Field(default_factory=list)
    video_level_tags: list[VisualTag] = Field(default_factory=list)
    recommended_industry: str | None = None
    recommended_strategy: str | None = None
    average_confidence: float = Field(default=0.0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    created_at: str


class UpdateSegmentVisualTagsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    primary_industry: str | None = None
    primary_scene: str | None = None
    primary_action: str | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        unknown = [item for item in cleaned if item not in TAG_CATEGORY_BY_NAME]
        if unknown:
            raise ValueError(f"Unsupported visual tags: {', '.join(unknown)}")
        return cleaned


class SilentVisualTaggingMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    recommended_industry: str = "general_product"
    recommended_strategy: str = "chill_immersive"
    average_confidence: float = Field(default=0.0, ge=0, le=1)
    tag_sources: dict[str, int] = Field(default_factory=dict)
    report_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
