from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublishStatus(str, Enum):
    draft = "draft"
    copied = "copied"
    posted = "posted"
    skipped = "skipped"


class OutputContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    output_index: int = Field(gt=0)
    video_path: str
    hook: str | None = None
    caption: str = Field(min_length=1)
    hashtags: list[str] = Field(default_factory=list)
    cta: str | None = None
    variant_style_id: str | None = None
    timeline_template_id: str | None = None
    publish_status: PublishStatus = PublishStatus.draft
    platform: str | None = None
    user_note: str | None = None
    created_at: str
    updated_at: str

    @field_validator("caption")
    @classmethod
    def clean_caption(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Caption không được để trống.")
        return cleaned

    @field_validator("hashtags", mode="before")
    @classmethod
    def clean_hashtags(cls, value: Any) -> list[str]:
        return normalize_hashtags(value)

    @field_validator("hook", "cta", "variant_style_id", "timeline_template_id", "platform", "user_note")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class ContentBatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_items: int
    draft: int
    copied: int
    posted: int
    skipped: int


def normalize_hashtags(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items: list[Any] = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = list(value) if hasattr(value, "__iter__") else [value]

    seen: set[str] = set()
    cleaned: list[str] = []
    for item in raw_items:
        for token in str(item).replace(",", " ").split():
            hashtag = token.strip()
            if not hashtag:
                continue
            if not hashtag.startswith("#"):
                hashtag = f"#{hashtag}"
            if hashtag not in seen:
                cleaned.append(hashtag)
                seen.add(hashtag)
    return cleaned


def build_content_summary(items: list[OutputContentItem]) -> ContentBatchSummary:
    counts = {status.value: 0 for status in PublishStatus}
    for item in items:
        counts[item.publish_status.value] += 1
    return ContentBatchSummary(
        total_items=len(items),
        draft=counts[PublishStatus.draft.value],
        copied=counts[PublishStatus.copied.value],
        posted=counts[PublishStatus.posted.value],
        skipped=counts[PublishStatus.skipped.value],
    )
