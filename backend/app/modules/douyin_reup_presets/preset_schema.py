from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings


class DouyinReupPresetMode(str, Enum):
    safe_review = "safe_review"
    fast_auto = "fast_auto"
    ocr_priority = "ocr_priority"
    voice_priority = "voice_priority"
    clean_subtitle_only = "clean_subtitle_only"
    music_recut = "music_recut"


class DouyinReupPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: DouyinReupPresetMode
    name: str
    description: str
    recommended_for: list[str] = Field(default_factory=list)
    not_recommended_for: list[str] = Field(default_factory=list)
    settings: DouyinReupSettings
    ui_badge: str
    is_default: bool = False
