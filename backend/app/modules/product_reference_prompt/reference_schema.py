from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductReferenceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    role: str
    local_path: str | None = None
    original_url: str | None = None
    width: int | None = None
    height: int | None = None
    quality_score: float | None = None
    user_note: str | None = None


class ProductReferenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    product_name: str
    brand: str | None = None
    industry_preset_id: str | None = None

    visual_identity: str
    product_accuracy_lock: list[str] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)

    reference_assets: list[ProductReferenceAsset] = Field(default_factory=list)
    main_product_asset_id: str | None = None

    warnings: list[str] = Field(default_factory=list)

    @field_validator("product_accuracy_lock", "allowed_claims", "forbidden_claims", "warnings")
    @classmethod
    def clean_unique_text(cls, value: list[str]) -> list[str]:
        return _clean_unique(value)


class StoryboardScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scene_index: int
    duration_seconds: float
    scene_type: str
    purpose: str
    visual_description: str
    camera_direction: str
    product_accuracy_notes: list[str] = Field(default_factory=list)
    subtitle_suggestion: str | None = None
    voiceover_suggestion: str | None = None

    @field_validator("product_accuracy_notes")
    @classmethod
    def clean_accuracy_notes(cls, value: list[str]) -> list[str]:
        return _clean_unique(value)


class ProductStoryboard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    title: str
    total_duration_seconds: float
    aspect_ratio: str = "9:16"
    scenes: list[StoryboardScene] = Field(default_factory=list)
    negative_prompt: list[str] = Field(default_factory=list)
    reference_assets: list[ProductReferenceAsset] = Field(default_factory=list)

    @field_validator("negative_prompt")
    @classmethod
    def clean_negative_prompt(cls, value: list[str]) -> list[str]:
        return _clean_unique(value)


class VideoPromptPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    product_name: str
    prompt_type: str
    model_hint: str | None = None

    product_reference_summary: ProductReferenceSummary
    storyboard: ProductStoryboard

    video_prompt: str
    negative_prompt: str
    short_prompt: str | None = None
    json_prompt: dict[str, Any] | None = None

    created_at: str


def _clean_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned
