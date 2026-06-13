from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SourceMediaType(str, Enum):
    video = "video"
    audio = "audio"
    image = "image"
    unknown = "unknown"


class SourceMediaOrientation(str, Enum):
    vertical = "vertical"
    horizontal = "horizontal"
    square = "square"
    unknown = "unknown"


class SourceMediaStatus(str, Enum):
    valid = "valid"
    unreadable = "unreadable"
    unsupported = "unsupported"
    missing = "missing"
    warning = "warning"


class SourceMediaQualityFlag(str, Enum):
    too_short = "too_short"
    too_long = "too_long"
    low_resolution = "low_resolution"
    horizontal_video = "horizontal_video"
    square_video = "square_video"
    no_audio = "no_audio"
    unreadable = "unreadable"
    duplicate_name = "duplicate_name"
    very_large_file = "very_large_file"


class SourceMediaItem(BaseModel):
    id: str
    folder_id: str | None = None

    path: str
    filename: str
    extension: str
    media_type: SourceMediaType = SourceMediaType.video
    status: SourceMediaStatus = SourceMediaStatus.valid

    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    bitrate: int | None = None
    codec: str | None = None
    has_audio: bool | None = None

    file_size_bytes: int = 0
    created_at: str | None = None
    modified_at: str | None = None

    orientation: SourceMediaOrientation = SourceMediaOrientation.unknown
    aspect_ratio: float | None = None

    thumbnail_path: str | None = None
    preview_path: str | None = None

    quality_score: float | None = None
    quality_flags: list[SourceMediaQualityFlag] = Field(default_factory=list)

    selected: bool = True
    excluded_reason: str | None = None
    priority: Literal["low", "normal", "high"] = "normal"

    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None


class SourceFolderScanRequest(BaseModel):
    folder_path: str
    recursive: bool = False

    include_extensions: list[str] = Field(default_factory=lambda: [".mp4", ".mov", ".mkv", ".webm"])
    max_files: int | None = Field(default=None, gt=0)

    generate_thumbnails: bool = True
    thumbnail_at_second: float = Field(default=1.0, ge=0)

    min_duration_seconds: float | None = Field(default=None, ge=0)
    max_duration_seconds: float | None = Field(default=None, ge=0)

    prefer_vertical: bool = True

    @field_validator("include_extensions")
    @classmethod
    def normalize_extensions(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            ext = item.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if ext not in cleaned:
                cleaned.append(ext)
        return cleaned or [".mp4", ".mov", ".mkv", ".webm"]


class SourceFolderScanResult(BaseModel):
    success: bool
    folder_path: str
    folder_id: str
    total_files_found: int = 0
    valid_videos: int = 0
    warning_videos: int = 0
    unreadable_files: int = 0

    vertical_count: int = 0
    horizontal_count: int = 0
    square_count: int = 0

    selected_count: int = 0
    items: list[SourceMediaItem] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SourceMediaSelectionRequest(BaseModel):
    folder_id: str
    selected_item_ids: list[str]
    excluded_item_ids: list[str] = Field(default_factory=list)
    priorities: dict[str, Literal["low", "normal", "high"]] = Field(default_factory=dict)
    selection_name: str | None = None


class SourceMediaSelectionResult(BaseModel):
    success: bool
    folder_id: str
    selection_id: str | None = None
    selected_count: int = 0
    excluded_count: int = 0
    selected_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
