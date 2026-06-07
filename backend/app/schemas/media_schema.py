from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.segment_scoring.scoring_schema import SegmentScore


class MediaFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    duration: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    has_audio: bool
    format_name: str


class VideoSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    source_path: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    duration: float = Field(gt=0)
    score: float = Field(ge=0, le=1)
    score_detail: SegmentScore | None = None
    tags: list[str] = Field(default_factory=list)
    user_review_status: str | None = None
    source_media_review_status: str | None = None
