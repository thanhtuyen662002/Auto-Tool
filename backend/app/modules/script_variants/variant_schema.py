from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.script_writer.script_writer import SubtitleLine, VoiceoverLine
from app.schemas.project_schema import ProductInfo


class ScriptVariantStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    hook_type: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    cta_style: str = Field(min_length=1)
    best_for_templates: list[str] = Field(default_factory=list)


class ScriptVariantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(gt=0)
    total_outputs: int = Field(gt=0)
    product: ProductInfo
    render_duration: float = Field(gt=0)
    timeline_template_id: str | None = None
    variant_style_id: str = Field(min_length=1)
    language: str = "vi"
    industry_preset_id: str | None = None
    industry_name: str | None = None
    caption_tone: str | None = None
    preferred_script_variant_ids: list[str] = Field(default_factory=list)
    hashtag_suggestions: list[str] = Field(default_factory=list)
    industry_notes: list[str] = Field(default_factory=list)


class ScriptVariantResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    output_index: int = Field(gt=0)
    variant_style_id: str = Field(min_length=1)
    industry_preset_id: str | None = None
    caption_tone: str | None = None
    hashtag_suggestions_used: list[str] = Field(default_factory=list)
    hook: str = Field(min_length=1)
    voiceover: list[VoiceoverLine] = Field(min_length=1)
    subtitles: list[SubtitleLine] = Field(min_length=1)
    cta: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    hashtags: list[str] = Field(default_factory=list)
