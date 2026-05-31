from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    description: str = Field(min_length=1)
    features: list[str] = Field(min_length=1)
    cta: str = Field(min_length=1)

    @field_validator("features")
    @classmethod
    def clean_features(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("features must contain at least one non-empty item")
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
