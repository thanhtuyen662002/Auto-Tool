from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.industry_presets.industry_schema import IndustrySettings
from app.modules.visual_style.style_schema import VisualStyleSettings


class ProductSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)

    @field_validator("name", "value")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ProductInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    brand: str = ""
    description: str = Field(min_length=1)
    features: list[str] = Field(min_length=1)
    specs: list[ProductSpec] = Field(default_factory=list)
    cta: str = Field(min_length=1)
    validation_warnings: list[str] = Field(default_factory=list)
    hashtag_suggestions: list[str] = Field(default_factory=list)

    @field_validator("features")
    @classmethod
    def clean_features(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("features must contain at least one non-empty item")
        return cleaned

    @field_validator("name", "brand", "description", "cta")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("validation_warnings", "hashtag_suggestions")
    @classmethod
    def clean_text_list(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item).strip().split())
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned


class RenderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_count: int = Field(gt=0)
    duration: float = Field(gt=0)
    aspect_ratio: str = Field(min_length=1)
    resolution: str = Field(min_length=3)
    fps: int = Field(gt=0)

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise ValueError("resolution must use WIDTHxHEIGHT format, for example 1080x1920")
        try:
            width, height = (int(part) for part in parts)
        except ValueError as exc:
            raise ValueError("resolution width and height must be integers") from exc
        if width <= 0 or height <= 0:
            raise ValueError("resolution width and height must be greater than 0")
        return f"{width}x{height}"


class EffectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cut_intensity: int = Field(ge=0, le=100)
    speed_variation: int = Field(ge=0, le=100)
    grain: int = Field(ge=0, le=100)
    zoom_motion: int = Field(ge=0, le=100)
    overlay_height: int = Field(ge=0, le=100)
    subtitle_size: int = Field(gt=0)


class AISettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_model: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    language: str = Field(min_length=1)
    gemini_api_keys: list[str] = Field(default_factory=list)

    @field_validator("gemini_api_keys")
    @classmethod
    def clean_gemini_api_keys(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            key = item.strip()
            if not key or key in seen:
                continue
            cleaned.append(key)
            seen.add(key)
        return cleaned


class MusicSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    source_folder: str | None = None
    source_file: str | None = None
    volume: float = Field(default=0.12, ge=0, le=1)
    fade_in: float = Field(default=0.5, ge=0)
    fade_out: float = Field(default=0.8, ge=0)
    duck_under_voice: bool = False


class TimelineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(default="ugc_reviewer_natural", min_length=1)


class ScriptVariationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(default="auto_mix", min_length=1)
    preferred_variant_ids: list[str] = Field(default_factory=list)

    @field_validator("preferred_variant_ids")
    @classmethod
    def clean_preferred_variant_ids(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            variant_id = item.strip()
            if not variant_id or variant_id in seen:
                continue
            cleaned.append(variant_id)
            seen.add(variant_id)
        return cleaned


class TTSSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "edge_tts"
    fallback_provider: str = "piper"
    voice: str = "vi-VN-HoaiMyNeural"
    language: str = "vi"
    api_key: str | None = None
    credentials_json_path: str | None = None
    access_token: str | None = None
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    output_format: str = "mp3"

    @field_validator("provider", "fallback_provider", "output_format")
    @classmethod
    def clean_identifier(cls, value: str) -> str:
        return value.strip().lower().replace("-", "_")


class CropSafetySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    mode: str = "auto_safe"
    allow_blur_background: bool = True
    reduce_zoom_on_risk: bool = True
    reduce_overlay_on_risk: bool = True

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        cleaned = value.strip().lower().replace("-", "_")
        allowed = {"auto_safe", "center_crop", "fit_blur_background"}
        if cleaned not in allowed:
            raise ValueError(f"crop safety mode must be one of: {', '.join(sorted(allowed))}")
        return cleaned


class CacheSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    cache_media_metadata: bool = True
    cache_segment_scoring: bool = True
    cache_crop_safety: bool = True
    cache_tts: bool = True
    cache_overlay_assets: bool = True
    clear_cache_before_render: bool = False


class SourceMediaSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    respect_user_exclusions: bool = True
    prefer_favorite_segments: bool = True
    allow_excluded_fallback: bool = False


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=1)
    source_folder: str = Field(min_length=1)
    output_folder: str = Field(min_length=1)
    product: ProductInfo
    render: RenderSettings
    effects: EffectSettings
    ai: AISettings
    music: MusicSettings = Field(default_factory=MusicSettings)
    timeline: TimelineSettings = Field(default_factory=TimelineSettings)
    script_variation: ScriptVariationSettings = Field(default_factory=ScriptVariationSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    visual_style: VisualStyleSettings = Field(default_factory=VisualStyleSettings)
    industry: IndustrySettings | None = None
    crop_safety: CropSafetySettings = Field(default_factory=CropSafetySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    source_media: SourceMediaSettings = Field(default_factory=SourceMediaSettings)
