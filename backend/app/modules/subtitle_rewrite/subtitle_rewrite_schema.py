from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine


class SubtitleRewriteStyle(str, Enum):
    short_natural = "short_natural"
    very_short = "very_short"
    casual_tiktok = "casual_tiktok"
    clear_review = "clear_review"
    sales_natural = "sales_natural"


class SubtitleRewriteSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    line_index: int
    source_text: str | None = None
    original_translation: str
    suggested_text: str
    style: SubtitleRewriteStyle
    reason: str | None = None
    char_count_before: int
    char_count_after: int
    estimated_cps_before: float | None = None
    estimated_cps_after: float | None = None
    safety_warnings: list[str] = Field(default_factory=list)
    quality_score_before: float | None = None
    quality_score_after: float | None = None
    created_at: str
    applied_at: str | None = None
    auto_applied: bool = False


class GenerateSubtitleRewriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: SubtitleRewriteStyle = SubtitleRewriteStyle.short_natural
    suggestion_count: int = Field(default=3, ge=1, le=3)
    max_chars: int | None = Field(default=None, ge=8, le=160)
    preserve_keywords: list[str] = Field(default_factory=list)
    use_ai: bool = True

    @field_validator("preserve_keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class ApplySubtitleRewriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_id: str
    refresh_quality_score: bool = True


class BulkRewriteFlaggedLinesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: SubtitleRewriteStyle = SubtitleRewriteStyle.short_natural
    max_lines: int = Field(default=20, ge=1, le=100)
    only_issue_types: list[str] = Field(default_factory=list)
    auto_apply_safe_suggestions: bool = False


class SubtitleRewriteSuggestionsResponse(BaseModel):
    success: bool = True
    items: list[SubtitleRewriteSuggestion] = Field(default_factory=list)


class ApplySubtitleRewriteResponse(BaseModel):
    success: bool = True
    line: SubtitleLine


class BulkSubtitleRewriteResponse(BaseModel):
    success: bool = True
    processed_lines: int
    suggestions_created: int
    auto_applied: int
    items: list[SubtitleRewriteSuggestion] = Field(default_factory=list)
