from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OCRRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int
    width: int
    height: int

    @field_validator("x", "y", "width", "height")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("OCR region values must be non-negative.")
        return value


class OCRFrameResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_ms: int
    frame_path: str | None = None
    region: OCRRegion
    text: str = ""
    confidence: float = 0.0
    raw_blocks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OCRSubtitleLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    start_ms: int
    end_ms: int
    text: str
    confidence: float
    frame_count: int
    warnings: list[str] = Field(default_factory=list)


class HardSubOCRResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    provider: str
    language: str
    region_mode: str
    source_srt_path: str | None = None
    debug_json_path: str | None = None
    frame_count: int
    detected_line_count: int
    average_confidence: float
    lines: list[OCRSubtitleLine]
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
