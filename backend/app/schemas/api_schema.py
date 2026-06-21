from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.content_manager.content_schema import ContentBatchSummary, OutputContentItem, PublishStatus
from app.modules.douyin_reup.douyin_schema import DouyinOutputResult, DouyinReupSettings, DouyinReupSummary, DouyinVideoItem
from app.modules.douyin_reup_presets.preset_schema import DouyinReupPreset
from app.modules.industry_presets.industry_schema import IndustryPreset
from app.modules.product_drafts.product_draft_schema import (
    ClearArchivedDraftsResponse,
    CreateProjectFromDraftRequest,
    CreateProjectFromDraftResponse,
    DeleteProductDraftResponse,
    ProductDraft,
    ProductDraftApplyResponse,
    ProductDraftListResponse,
    ProjectListResponse as ProductDraftProjectListResponse,
    UpdateProductDraftRequest,
)
from app.modules.product_import.product_import_schema import ProductImportResult, ProductInfoNormalized, RawProductInput
from app.modules.product_reference_prompt.reference_schema import (
    ProductReferenceSummary,
    ProductStoryboard,
    VideoPromptPack,
)
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan
from app.modules.silent_caption_templates.caption_template_schema import SilentCaptionTemplate
from app.modules.silent_visual_tagging.visual_tag_schema import VideoVisualTagReport
from app.modules.source_media_manager.media_manager_schema import (
    BulkSegmentReviewResponse,
    MediaReviewStatus,
    SegmentReviewResponse,
    SegmentReviewStatus,
    SourceMediaResponse,
    UpdateSegmentReviewResponse,
    UpdateSourceMediaReviewResponse,
)
from app.modules.visual_style.style_schema import OverlayStyle, SubtitleStyle
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


class ProjectListResponse(ProductDraftProjectListResponse):
    pass


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gemini_api_keys: list[str] = Field(default_factory=list)
    google_tts_credentials_json_path: str | None = None
    google_tts_api_key: str | None = None
    google_tts_access_token: str | None = None
    google_tts_favorite_voices: list[str] = Field(default_factory=list)
    google_tts_preview_text: str = "Xin chào, đây là giọng đọc thử của Auto Tool."
    favorite_music_paths: list[str] = Field(default_factory=list)

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

    @field_validator("google_tts_favorite_voices", "favorite_music_paths")
    @classmethod
    def clean_unique_strings(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned

    @field_validator("google_tts_preview_text")
    @classmethod
    def clean_google_tts_preview_text(cls, value: str) -> str:
        cleaned = (value or "").strip()
        return cleaned or "Xin chào, đây là giọng đọc thử của Auto Tool."

    @field_validator("google_tts_credentials_json_path", "google_tts_api_key", "google_tts_access_token")
    @classmethod
    def clean_optional_secret(cls, value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None


class ConfigRequirementIssue(BaseModel):
    severity: Literal["error", "warning"] = "error"
    code: str
    field: str
    message: str
    action: str


class ConfigRequirementCheckRequest(BaseModel):
    project_config: ProjectConfig | None = None
    project_id: str | None = None
    mode: Literal["product_render", "douyin_reup", "silent_reup", "subtitle_render"] = "product_render"


class ConfigRequirementCheckResponse(BaseModel):
    ready: bool
    errors_count: int = 0
    warnings_count: int = 0
    issues: list[ConfigRequirementIssue] = Field(default_factory=list)


class BrowsePathRequest(BaseModel):
    mode: str = Field(default="folder", pattern="^(file|folder)$")
    title: str | None = None
    initial_path: str | None = None
    extensions: list[str] = Field(default_factory=list)


class BrowsePathResponse(BaseModel):
    path: str | None = None
    cancelled: bool = False


class SystemDependencyStatusResponse(BaseModel):
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    piper_path: str | None = None
    piper_model_path: str | None = None
    piper_config_path: str | None = None
    ocr_provider: str | None = None
    ocr_available: bool = False
    ocr_message: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ScanResponse(BaseModel):
    total_files: int
    valid_videos: int
    invalid_files: int
    media: list[MediaFile]


class DouyinReupScanRequest(BaseModel):
    source_folder: str = Field(min_length=1)


class DouyinReupScanResponse(BaseModel):
    total_files: int
    valid_videos: int
    invalid_files: int
    media: list[DouyinVideoItem]
    errors: list[str] = Field(default_factory=list)


class DouyinOcrTestRequest(BaseModel):
    video_path: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)


class DouyinOcrTestResponse(BaseModel):
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class DouyinReupProcessRequest(BaseModel):
    project_name: str = Field(min_length=1)
    source_folder: str = Field(min_length=1)
    output_folder: str = Field(min_length=1)
    settings: DouyinReupSettings = Field(default_factory=lambda: DouyinReupSettings(enabled=True))
    selected_video_paths: list[str] = Field(default_factory=list)
    source_selection_id: str | None = None


class DouyinReupProcessResponse(BaseModel):
    project_id: str
    job_id: str
    status: str


class DouyinReupPresetListResponse(BaseModel):
    presets: list[DouyinReupPreset]


class DouyinApplyPresetRequest(BaseModel):
    preset_id: str = "safe_review"
    current_settings: DouyinReupSettings | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class DouyinApplyPresetResponse(BaseModel):
    preset: DouyinReupPreset
    settings: DouyinReupSettings


class DouyinOneClickBatchRequest(BaseModel):
    project_name: str = Field(min_length=1)
    source_folder: str = Field(min_length=1)
    output_folder: str = Field(min_length=1)
    preset_id: str = "safe_review"
    bgm_folder: str | None = None
    visual_style_preset_id: str | None = None
    process_mode: Literal["all_videos", "first_n", "selected"] = "all_videos"
    max_videos: int | None = Field(default=None, gt=0)
    selected_video_paths: list[str] = Field(default_factory=list)
    source_selection_id: str | None = None
    review_subtitles_before_render: bool | None = None
    auto_render_after_translation: bool | None = None
    product_context: dict[str, Any] = Field(default_factory=dict)
    advanced_overrides: dict[str, Any] = Field(default_factory=dict)


class DouyinOneClickBatchResponse(BaseModel):
    project_id: str
    job_id: str
    status: str
    preset_id: str
    preset_name: str
    total_outputs: int


class DouyinPresetRecommendationRequest(BaseModel):
    source_folder: str = Field(min_length=1)
    current_settings: DouyinReupSettings | None = None


class DouyinPresetRecommendationResponse(BaseModel):
    preset_id: str
    preset_name: str
    reason: str
    confidence: float = Field(ge=0, le=1)
    signals: dict[str, Any] = Field(default_factory=dict)


class DouyinRetryFailedRequest(BaseModel):
    retry_steps: list[str] = Field(default_factory=lambda: ["asr", "translation", "render"])
    settings: dict[str, Any] = Field(default_factory=dict)


class DouyinRetryWithPresetRequest(BaseModel):
    preset_id: str = "safe_review"
    video_ids: list[str] = Field(default_factory=list)
    retry_steps: list[str] = Field(default_factory=lambda: ["asr", "translation", "render"])
    settings: dict[str, Any] = Field(default_factory=dict)
    advanced_overrides: dict[str, Any] = Field(default_factory=dict)


class DouyinRetryCustomRequest(BaseModel):
    retry_mode: Literal["render_only", "read_screen_text", "rebuild_subtitle"] = "render_only"
    video_ids: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    include_unfinished: bool = True


class DouyinRetryFailedResponse(BaseModel):
    job_id: str
    status: str
    retry_outputs: int


class DouyinReupJobResultsResponse(BaseModel):
    summary: DouyinReupSummary | None = None
    outputs: list[DouyinOutputResult] = Field(default_factory=list)


class SilentReupDetectRequest(BaseModel):
    source_folder: str = Field(min_length=1)


class SilentReupDetectItem(BaseModel):
    video_path: str
    has_speech: bool
    speech_score: float
    recommended_mode: str
    method: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SilentReupDetectResponse(BaseModel):
    success: bool
    items: list[SilentReupDetectItem] = Field(default_factory=list)


class SilentReupPlanRequest(BaseModel):
    video_path: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)
    product_context: dict[str, Any] = Field(default_factory=dict)


class SilentReupPlanResponse(BaseModel):
    success: bool
    plan_id: str
    plan: SilentReupPlan


class SilentReupRenderRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)


class SilentReupRenderResponse(BaseModel):
    success: bool
    job_id: str


class SilentCaptionRegenerateRequest(BaseModel):
    industry: str = "auto"
    tone: str = "natural"
    strategy: str | None = None
    use_visual_tags: bool = True
    respect_user_tag_overrides: bool = True


class SilentCaptionTemplateListResponse(BaseModel):
    items: list[SilentCaptionTemplate] = Field(default_factory=list)
    total: int = 0


class SilentCaptionIndustriesResponse(BaseModel):
    items: list[dict[str, str]] = Field(default_factory=list)


class SilentReupReviewDocumentResponse(BaseModel):
    success: bool
    document_id: str


class SilentVisualTagReportResponse(BaseModel):
    success: bool
    report: VideoVisualTagReport


class SilentVisualTagVocabularyResponse(BaseModel):
    industry: list[str] = Field(default_factory=list)
    scene: list[str] = Field(default_factory=list)
    action: list[str] = Field(default_factory=list)
    product_stage: list[str] = Field(default_factory=list)
    quality: list[str] = Field(default_factory=list)


class SilentReupOneClickRequest(BaseModel):
    project_name: str = Field(min_length=1)
    source_folder: str = Field(min_length=1)
    output_folder: str = Field(min_length=1)
    strategy: str = "chill_immersive"
    visual_style_preset_id: str | None = None
    bgm_folder: str | None = None
    process_mode: Literal["all_videos", "first_n", "selected"] = "all_videos"
    max_videos: int | None = Field(default=None, gt=0)
    selected_video_paths: list[str] = Field(default_factory=list)
    source_selection_id: str | None = None
    review_before_render: bool = True
    product_context: dict[str, Any] = Field(default_factory=dict)
    advanced_overrides: dict[str, Any] = Field(default_factory=dict)


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


class UpdateSourceMediaReviewRequest(BaseModel):
    review_status: MediaReviewStatus
    user_note: str | None = None
    media_path: str


class UpdateSegmentReviewRequest(BaseModel):
    review_status: SegmentReviewStatus
    user_note: str | None = None


class BulkSegmentReviewRequest(BaseModel):
    segment_ids: list[str] = Field(default_factory=list)
    review_status: SegmentReviewStatus
    user_note: str | None = None


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
    cache_summary: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


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


class TTSPreviewRequest(BaseModel):
    provider: str = "google_cloud_tts"
    voice: str = Field(min_length=1)
    text: str = "Xin chào, đây là giọng đọc thử của Auto Tool."
    language: str = "vi"
    api_key: str | None = None
    credentials_json_path: str | None = None
    access_token: str | None = None


class TTSPreviewResponse(BaseModel):
    success: bool
    path: str
    url: str
    provider: str
    voice: str
    warnings: list[str] = Field(default_factory=list)


class MusicLibraryTrack(BaseModel):
    path: str
    filename: str
    size_bytes: int = 0
    duration: float | None = None
    favorite: bool = False


class MusicLibraryResponse(BaseModel):
    folder_path: str | None = None
    tracks: list[MusicLibraryTrack] = Field(default_factory=list)
    favorite_music_paths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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


class VisualStylePresetItem(BaseModel):
    id: str
    name: str
    description: str
    category: str
    recommended_for: list[str] = Field(default_factory=list)
    subtitle: SubtitleStyle | None = None
    overlay: OverlayStyle | None = None


class VisualStylePresetsResponse(BaseModel):
    presets: list[VisualStylePresetItem]


class VisualStylePreviewRequest(BaseModel):
    preset_id: str
    sample_text: str = "Nhỏ gọn, dễ dùng, phù hợp mỗi ngày"
    resolution: str = "1080x1920"


class VisualStylePreviewResponse(BaseModel):
    success: bool
    preview_image_path: str
    preview_image_url: str | None = None


class UpdateProjectVisualStyleRequest(BaseModel):
    preset_id: str


class UpdateProjectVisualStyleResponse(BaseModel):
    success: bool
    visual_style: dict[str, Any]


class ReferenceSummaryResponse(BaseModel):
    success: bool
    summary: ProductReferenceSummary


class StoryboardRequest(BaseModel):
    duration_seconds: float = Field(default=8, gt=0, le=120)
    scene_count: int = Field(default=5, gt=0, le=12)
    style: str | None = None


class StoryboardResponse(BaseModel):
    success: bool
    storyboard: ProductStoryboard


class VideoPromptPackRequest(BaseModel):
    duration_seconds: float = Field(default=8, gt=0, le=120)
    scene_count: int = Field(default=5, gt=0, le=12)
    model_hint: str | None = None
    style: str | None = None


class VideoPromptPackResponse(BaseModel):
    success: bool
    prompt_pack: VideoPromptPack
    files: dict[str, str] = Field(default_factory=dict)


class IndustryPresetsResponse(BaseModel):
    presets: list[IndustryPreset]


class ApplyIndustryPresetRequest(BaseModel):
    preset_id: str
    apply_visual_style: bool = True
    apply_timeline: bool = True
    apply_script_variation: bool = True
    apply_tts_voice: bool = True
    apply_edit_strength: bool = True


class ApplyIndustryPresetResponse(BaseModel):
    success: bool
    project_id: str
    preset_id: str
    updated_config: ProjectConfig


class ProductInfoImportRequest(RawProductInput):
    save_to_inbox: bool = False
    extractor_debug: dict[str, Any] | None = None


class ProductInfoImportResponse(ProductImportResult):
    pass


class UpdateProjectProductInfoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductInfoNormalized


class UpdateProjectProductInfoResponse(BaseModel):
    success: bool
    project_id: str
    product: ProductInfoNormalized
    updated_config: ProjectConfig


class HealthResponse(BaseModel):
    status: str
    version: str = "unknown"
    capabilities: dict[str, bool] = Field(default_factory=dict)
    recoverable_jobs_count: int = 0


class UpdateCheckResponse(BaseModel):
    has_update: bool
    current_version: str
    latest_version: str
    download_url: str | None = None
    html_url: str | None = None
    release_name: str | None = None
    release_notes: str | None = None
    error: str | None = None


class UpdateDownloadResponse(BaseModel):
    success: bool
    extract_dir: str | None = None
    updater_script: str | None = None
    message: str = ""
    error: str | None = None


class ErrorResponse(BaseModel):
    detail: str


class ProjectConfigPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    payload: dict[str, Any] = Field(default_factory=dict)
