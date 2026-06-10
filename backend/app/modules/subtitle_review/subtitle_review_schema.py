from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.subtitle_quality.subtitle_quality_schema import SubtitleQualityIssue


class SubtitleReviewStatus(str, Enum):
    pending = "pending"
    reviewed = "reviewed"
    needs_fix = "needs_fix"
    approved = "approved"


class SubtitleLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    start_ms: int
    end_ms: int
    source_text: str | None = None
    translated_text: str
    edited_text: str | None = None
    status: SubtitleReviewStatus = SubtitleReviewStatus.pending
    warnings: list[str] = Field(default_factory=list)
    user_note: str | None = None
    quality_score: float | None = None
    quality_needs_review: bool = False
    quality_severity: str | None = None
    quality_issues: list[SubtitleQualityIssue] = Field(default_factory=list)
    rewrite_history: list[dict] = Field(default_factory=list)

    @field_validator("source_text", "translated_text", "edited_text", "user_note")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        return cleaned or None

    @field_validator("warnings")
    @classmethod
    def clean_warnings(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item).strip().split())
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned


class SubtitleReviewDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str | None = None
    job_id: str | None = None
    video_id: str
    video_path: str
    source_language: str = "zh"
    target_language: str = "vi"
    source_type: str | None = None
    source_srt_path: str | None = None
    translated_srt_path: str
    corrected_srt_path: str | None = None
    corrected_ass_path: str | None = None
    status: SubtitleReviewStatus = SubtitleReviewStatus.pending
    lines: list[SubtitleLine]
    line_count: int
    reviewed_count: int = 0
    edited_count: int = 0
    warning_count: int = 0
    quality_average_score: float | None = None
    quality_needs_review_count: int = 0
    quality_critical_count: int = 0
    quality_warning_count: int = 0
    approval_quality_warning: str | None = None
    approval_quality_guard: dict | None = None
    created_at: str
    updated_at: str


class UpdateSubtitleLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edited_text: str | None = None
    status: SubtitleReviewStatus | None = None
    user_note: str | None = None


class BulkUpdateSubtitleLinesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_indexes: list[int]
    status: SubtitleReviewStatus | None = None


class SaveSubtitleReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[SubtitleLine]
    mark_as_reviewed: bool = False


class ApproveSubtitleDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate_ass: bool = True
    visual_style_preset_id: str | None = None


class RenderSubtitleReviewDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_folder: str
    settings: DouyinReupSettings = Field(default_factory=lambda: DouyinReupSettings(enabled=True))


class RenderApprovedSubtitleDocumentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str | None = None
    project_id: str | None = None
    output_folder: str
    settings: DouyinReupSettings = Field(default_factory=lambda: DouyinReupSettings(enabled=True))


class SubtitleReviewRenderResponse(BaseModel):
    job_id: str
    status: str


class SubtitleReviewDocumentListResponse(BaseModel):
    items: list[SubtitleReviewDocument]
