from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.content_manager.content_schema import ContentBatchSummary, OutputContentItem, PublishStatus
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.output_review.review_schema import OutputReviewStatus, OutputReviewSummary
from app.schemas.media_schema import MediaFile
from app.schemas.project_schema import ProjectConfig


class ProjectCreateResponse(BaseModel):
    project_id: str
    status: str


class ProjectDetailResponse(BaseModel):
    project_id: str
    status: str
    config: ProjectConfig
    created_at: str
    updated_at: str


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gemini_api_keys: list[str] = Field(default_factory=list)
    google_tts_credentials_json_path: str | None = None
    google_tts_api_key: str | None = None
    google_tts_access_token: str | None = None

    @field_validator("gemini_api_keys")
    @classmethod
    def clean_gemini_api_keys(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            key = str(item).strip()
            if not key or key in seen:
                continue
            cleaned.append(key)
            seen.add(key)
        return cleaned

    @field_validator("google_tts_credentials_json_path", "google_tts_api_key", "google_tts_access_token")
    @classmethod
    def clean_optional_secret(cls, value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None


class ScanResponse(BaseModel):
    total_files: int
    valid_videos: int
    invalid_files: int
    media: list[MediaFile]


class SegmentScoringResponse(BaseModel):
    total_segments: int
    usable_segments: int
    rejected_segments: int
    average_score: float
    rejection_summary: dict[str, int]
    report_path: str | None = None


class RenderRequest(BaseModel):
    preview_only: bool = False


class RenderResponse(BaseModel):
    job_id: str
    status: str


class LatestScriptResponse(BaseModel):
    script: ProductVideoScript | None = None


class JobLogItem(BaseModel):
    created_at: str
    level: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str
    progress: int
    total_outputs: int
    completed_outputs: int
    failed_outputs: int
    logs: list[JobLogItem]


class JobOutputItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    path: str
    status: str


class JobResultsResponse(BaseModel):
    outputs: list[JobOutputItem]


class OutputReviewItem(BaseModel):
    output_index: int
    video_path: str
    status: str
    overall_score: float
    technical_score: float
    segment_score: float
    audio_score: float
    subtitle_score: float
    timeline_score: float
    recommended_action: str
    review_status: OutputReviewStatus
    user_note: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class OutputReviewResponse(BaseModel):
    summary: OutputReviewSummary
    outputs: list[OutputReviewItem]


class UpdateOutputReviewRequest(BaseModel):
    review_status: OutputReviewStatus
    user_note: str | None = None


class UpdateOutputReviewResponse(BaseModel):
    success: bool
    output_index: int
    review_status: OutputReviewStatus


class RerenderRequest(BaseModel):
    mode: str = "selected"
    output_indexes: list[int] = Field(default_factory=list)
    reuse_script: bool = True
    reuse_timeline: bool = False
    reuse_settings: bool = True


class RerenderResponse(BaseModel):
    job_id: str
    status: str
    rerender_outputs: list[int]


class PresetItem(BaseModel):
    name: str
    effects: dict[str, int]
    timeline_template_id: str | None = None


class TimelineTemplateItem(BaseModel):
    id: str
    name: str
    description: str


class TimelineTemplatesResponse(BaseModel):
    templates: list[TimelineTemplateItem]


class ScriptVariantStyleItem(BaseModel):
    id: str
    name: str
    description: str
    hook_type: str
    tone: str
    cta_style: str
    best_for_templates: list[str] = Field(default_factory=list)


class ScriptVariantStylesResponse(BaseModel):
    styles: list[ScriptVariantStyleItem]


class TTSProviderItem(BaseModel):
    id: str
    name: str
    requires_api_key: bool
    online: bool
    recommended: bool


class TTSProvidersResponse(BaseModel):
    providers: list[TTSProviderItem]


class TTSVoicesRequest(BaseModel):
    api_key: str | None = None
    credentials_json_path: str | None = None
    access_token: str | None = None
    language_code: str = "vi-VN"


class TTSVoiceItem(BaseModel):
    name: str
    language_codes: list[str] = Field(default_factory=list)
    ssml_gender: str = ""
    natural_sample_rate_hertz: int = 0


class TTSVoicesResponse(BaseModel):
    voices: list[TTSVoiceItem]


class GenerateScriptVariantsRequest(BaseModel):
    output_count: int | None = None
    timeline_template_id: str | None = None


class ScriptVariantSummaryItem(BaseModel):
    output_index: int
    variant_style_id: str
    hook: str


class GenerateScriptVariantsResponse(BaseModel):
    total_variants: int
    variants: list[ScriptVariantSummaryItem]
    report_path: str | None = None


class ContentItemsResponse(BaseModel):
    summary: ContentBatchSummary
    items: list[OutputContentItem]


class UpdateContentItemRequest(BaseModel):
    hook: str | None = None
    caption: str | None = None
    hashtags: list[str] | str | None = None
    cta: str | None = None
    publish_status: PublishStatus | None = None
    platform: str | None = None
    user_note: str | None = None


class UpdateContentItemResponse(BaseModel):
    success: bool
    item: OutputContentItem


class MarkPostedRequest(BaseModel):
    platform: str | None = None


class ExportContentRequest(BaseModel):
    formats: list[str] = Field(default_factory=lambda: ["json", "csv", "txt", "md"])


class ContentExportFile(BaseModel):
    format: str
    path: str


class ContentExportResponse(BaseModel):
    success: bool
    files: list[ContentExportFile]


class HealthResponse(BaseModel):
    status: str
    version: str = "unknown"


class ErrorResponse(BaseModel):
    detail: str


class ProjectConfigPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    payload: dict[str, Any] = Field(default_factory=dict)
