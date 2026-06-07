from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MediaReviewStatus(str, Enum):
    pending = "pending"
    good = "good"
    bad = "bad"
    excluded = "excluded"
    favorite = "favorite"


class SegmentReviewStatus(str, Enum):
    pending = "pending"
    good = "good"
    bad = "bad"
    excluded = "excluded"
    favorite = "favorite"


class SourceMediaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    path: str
    filename: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    format_name: str
    orientation: str
    aspect_ratio: str
    quality_score: float | None = None
    segment_count: int = 0
    usable_segment_count: int = 0
    rejected_segment_count: int = 0
    review_status: MediaReviewStatus = MediaReviewStatus.pending
    user_note: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class SegmentReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    segment_id: str
    source_media_id: str
    source_path: str
    start: float
    end: float
    duration: float
    overall_score: float
    brightness_score: float | None = None
    sharpness_score: float | None = None
    motion_score: float | None = None
    freeze_score: float | None = None
    stability_score: float | None = None
    crop_safety_score: float | None = None
    crop_mode: str | None = None
    tags: list[str] = Field(default_factory=list)
    reject_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_status: SegmentReviewStatus = SegmentReviewStatus.pending
    user_note: str | None = None
    preview_thumbnail_path: str | None = None
    created_at: str
    updated_at: str


class SourceMediaSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_media: int
    good_media: int
    excluded_media: int
    bad_media: int
    total_segments: int
    usable_segments: int
    excluded_segments: int
    favorite_segments: int
    average_media_score: float | None = None
    average_segment_score: float | None = None


class SourceMediaResponse(BaseModel):
    summary: SourceMediaSummary
    items: list[SourceMediaItem]


class SegmentReviewResponse(BaseModel):
    items: list[SegmentReviewItem]


class UpdateSourceMediaReviewResponse(BaseModel):
    success: bool
    item: SourceMediaItem


class UpdateSegmentReviewResponse(BaseModel):
    success: bool
    item: SegmentReviewItem


class BulkSegmentReviewResponse(BaseModel):
    success: bool
    updated_count: int
