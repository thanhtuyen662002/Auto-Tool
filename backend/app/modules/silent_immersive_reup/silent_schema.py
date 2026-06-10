from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeechPresenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    has_speech: bool
    speech_score: float = Field(ge=0, le=1)
    audio_energy_score: float | None = Field(default=None, ge=0, le=1)
    speech_segments_count: int = 0
    method: str
    warnings: list[str] = Field(default_factory=list)


class VisualSegmentType(str, Enum):
    product_reveal = "product_reveal"
    unboxing = "unboxing"
    closeup = "closeup"
    demo = "demo"
    before_after = "before_after"
    usage_scene = "usage_scene"
    result = "result"
    transition = "transition"
    unknown = "unknown"


class SilentVisualSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    video_path: str
    start: float
    end: float
    duration: float
    segment_type: VisualSegmentType = VisualSegmentType.unknown
    visual_score: float = Field(default=0.0, ge=0, le=1)
    motion_score: float | None = Field(default=None, ge=0, le=1)
    sharpness_score: float | None = Field(default=None, ge=0, le=1)
    brightness_score: float | None = Field(default=None, ge=0, le=1)
    representative_frame_path: str | None = None
    ocr_text: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    caption_suggestion: str | None = None
    voiceover_suggestion: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ImmersiveCaptionLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    start: float
    end: float
    text: str
    source: Literal["ocr_translation", "visual_generated", "template", "manual"] = "visual_generated"
    segment_id: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join(value.replace("\r", " ").replace("\n", " ").split())
        if not cleaned:
            raise ValueError("Caption không được để trống.")
        return cleaned


class SilentReupPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    strategy: str
    has_speech: bool
    speech_score: float = Field(ge=0, le=1)
    visual_segments: list[SilentVisualSegment]
    captions: list[ImmersiveCaptionLine]
    generate_voiceover: bool = False
    voiceover_script: str | None = None
    recommended_audio_mode: str
    warnings: list[str] = Field(default_factory=list)


class SilentReupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_video_path: str
    output_video_path: str | None = None
    plan_path: str | None = None
    caption_srt_path: str | None = None
    caption_ass_path: str | None = None
    voiceover_path: str | None = None
    bgm_path: str | None = None
    status: Literal["success", "failed", "needs_review"] = "needs_review"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
