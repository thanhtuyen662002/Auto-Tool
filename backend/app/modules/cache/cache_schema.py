from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CacheEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    key: str
    hit: bool


class CacheRunStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    hits: int = 0
    misses: int = 0
    media_metadata_hits: int = 0
    media_metadata_misses: int = 0
    segment_score_hits: int = 0
    segment_score_misses: int = 0
    crop_safety_hits: int = 0
    crop_safety_misses: int = 0
    tts_hits: int = 0
    tts_misses: int = 0
    overlay_hits: int = 0
    overlay_misses: int = 0
    cache_lookup_seconds: float = 0.0
    cache_read_seconds: float = 0.0
    cache_write_seconds: float = 0.0
    cache_saved_estimated_seconds: float = 0.0
    events: list[CacheEvent] = Field(default_factory=list)


class CacheSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    hits: int = 0
    misses: int = 0
    cache_size_mb: float = 0.0
    items: dict[str, int] = Field(default_factory=dict)

