from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IndustrySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str | None = None

    @field_validator("preset_id")
    @classmethod
    def clean_preset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IndustryPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    recommended_for: list[str] = Field(default_factory=list)

    default_video_style: str = Field(min_length=1)
    default_edit_strength: str = Field(min_length=1)

    timeline_template_id: str = Field(min_length=1)
    visual_style_preset_id: str = Field(min_length=1)

    script_variation_mode: str = "auto_mix"
    preferred_script_variant_ids: list[str] = Field(default_factory=list)

    default_tts_voice: str = "vi-VN-HoaiMyNeural"
    caption_tone: str = Field(min_length=1)
    hashtag_suggestions: list[str] = Field(default_factory=list)

    render_defaults: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

