from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import database
from app.adapters.ffmpeg_adapter import FFmpegError
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.content_manager.content_schema import build_content_summary
from app.modules.content_manager.content_service import ContentService
from app.modules.cache.cache_service import CacheService
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.content_safety.safety_schema import SafetyCheckResult, SafetyIssue, build_safety_result
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService, build_retry_cache
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.douyin_reup_presets import DouyinReupPresetService
from app.modules.hardsub_ocr import HardSubOCRService
from app.modules.final_output_qa import (
    CreateExportPackRequest,
    FinalOutputQACheckRequest,
    FinalOutputQACheckResponse,
    FinalOutputQAJobRequest,
    FinalOutputQAJobResponse,
    PlatformExportPackResponse,
    PlatformTarget,
)
from app.modules.final_output_qa.export_pack_service import ExportPackService
from app.modules.final_output_qa.final_output_qa_service import FinalOutputQAService, build_final_qa_summary
from app.modules.industry_presets.industry_registry import get_industry_preset
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.industry_presets.industry_schema import IndustryPreset, IndustrySettings
from app.modules.output_review.review_service import OutputQualityReviewService, build_review_rows
from app.modules.product_drafts import CreateProductDraftRequest, ProductDraftService
from app.modules.product_assets import (
    AttachDraftAssetsRequest,
    AttachDraftAssetsResponse,
    ImportAssetsFromDraftRequest,
    ProductAssetListResponse,
    ProductAssetService,
    ProductAssetsImportResponse,
    UpdateProductAssetRequest,
)
from app.modules.product_import import ProductImportService, suggest_industry_preset, to_project_product_info
from app.modules.product_reference_prompt import ProductReferencePromptService
from app.modules.subtitle_review import (
    ApproveSubtitleDocumentRequest,
    RenderApprovedSubtitleDocumentsRequest,
    RenderSubtitleReviewDocumentRequest,
    SaveSubtitleReviewRequest,
    SubtitleReviewDocument,
    SubtitleReviewDocumentListResponse,
    SubtitleReviewRenderResponse,
    SubtitleReviewService,
    SubtitleLine,
    UpdateSubtitleLineRequest,
)
from app.modules.subtitle_quality.subtitle_quality_schema import (
    SubtitleDocumentQualityReport,
    SubtitleQualityFlaggedLinesResponse,
    SubtitleRewriteSuggestionRequest,
    SubtitleRewriteSuggestionResponse,
)
from app.modules.subtitle_quality.subtitle_quality_service import SubtitleQualityService
from app.modules.subtitle_rewrite import (
    ApplySubtitleRewriteRequest,
    ApplySubtitleRewriteResponse,
    BulkRewriteFlaggedLinesRequest,
    BulkSubtitleRewriteResponse,
    GenerateSubtitleRewriteRequest,
    SubtitleRewriteSuggestionsResponse,
)
from app.modules.subtitle_rewrite.subtitle_rewrite_service import SubtitleRewriteService
from app.modules.product_import.product_import_schema import (
    ProductImportDraftSummary,
    ProductImportSource,
    ProductInfoNormalized,
)
from app.modules.product_import.product_normalizer import ProductNormalizer
from app.modules.product_import.product_validator import ProductValidator
from app.modules.output_review.rerender_service import RerenderService
from app.modules.render_worker.render_worker import render_project
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.segmenter.segmenter import Segmenter
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_variants.variant_registry import list_variant_styles
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.source_media_manager.media_manager_service import MediaManagerService, build_source_media_summary
from app.modules.source_media_manager.segment_review_service import SegmentReviewService
from app.modules.timeline_templates.template_registry import list_timeline_templates
from app.modules.tts.tts_manager import list_tts_providers
from app.modules.tts.providers.google_cloud_tts_provider import list_google_cloud_voices
from app.modules.tts.providers.base import TTSProviderError
from app.modules.visual_style.style_registry import get_visual_style_preset, list_visual_style_presets
from app.modules.visual_style.visual_style_service import VisualStyleService
from app.presets import get_default_presets
from app.schemas.api_schema import (
    AppSettings,
    ApplyIndustryPresetRequest,
    ApplyIndustryPresetResponse,
    BrowsePathRequest,
    BrowsePathResponse,
    BulkSegmentReviewRequest,
    BulkSegmentReviewResponse,
    ContentExportFile,
    ContentExportResponse,
    ContentItemsResponse,
    DouyinReupJobResultsResponse,
    DouyinApplyPresetRequest,
    DouyinApplyPresetResponse,
    DouyinOneClickBatchRequest,
    DouyinOneClickBatchResponse,
    DouyinOcrTestRequest,
    DouyinOcrTestResponse,
    DouyinPresetRecommendationRequest,
    DouyinPresetRecommendationResponse,
    DouyinReupPresetListResponse,
    DouyinReupProcessRequest,
    DouyinReupProcessResponse,
    DouyinReupScanRequest,
    DouyinReupScanResponse,
    DouyinRetryFailedRequest,
    DouyinRetryFailedResponse,
    DouyinRetryWithPresetRequest,
    ExportContentRequest,
    HealthResponse,
    IndustryPresetsResponse,
    GenerateScriptVariantsRequest,
    GenerateScriptVariantsResponse,
    JobResultsResponse,
    JobStatusResponse,
    LatestScriptResponse,
    OutputReviewResponse,
    PresetItem,
    ProductInfoImportRequest,
    ProductInfoImportResponse,
    ProductDraft,
    ProductDraftApplyResponse,
    ProductDraftListResponse,
    ProjectListResponse,
    ReferenceSummaryResponse,
    UpdateProductDraftRequest,
    CreateProjectFromDraftRequest,
    CreateProjectFromDraftResponse,
    DeleteProductDraftResponse,
    ClearArchivedDraftsResponse,
    ProjectCreateResponse,
    ProjectDetailResponse,
    RenderRequest,
    RenderResponse,
    RerenderRequest,
    RerenderResponse,
    ScanResponse,
    SegmentReviewResponse,
    SegmentScoringResponse,
    ScriptVariantStyleItem,
    ScriptVariantStylesResponse,
    ScriptVariantSummaryItem,
    SourceMediaResponse,
    StoryboardRequest,
    StoryboardResponse,
    SystemDependencyStatusResponse,
    TTSProviderItem,
    TTSProvidersResponse,
    TTSVoiceItem,
    TTSVoicesRequest,
    TTSVoicesResponse,
    TimelineTemplateItem,
    TimelineTemplatesResponse,
    MarkPostedRequest,
    UpdateOutputReviewRequest,
    UpdateOutputReviewResponse,
    UpdateContentItemRequest,
    UpdateContentItemResponse,
    UpdateProjectProductInfoRequest,
    UpdateProjectProductInfoResponse,
    UpdateProjectVisualStyleRequest,
    UpdateProjectVisualStyleResponse,
    UpdateSegmentReviewRequest,
    UpdateSegmentReviewResponse,
    UpdateSourceMediaReviewRequest,
    UpdateSourceMediaReviewResponse,
    VisualStylePresetItem,
    VisualStylePresetsResponse,
    VisualStylePreviewRequest,
    VisualStylePreviewResponse,
    VideoPromptPackRequest,
    VideoPromptPackResponse,
)
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json
from app.utils.app_paths import app_data_dir, frontend_dist_dir
from app.utils.dependency_manager import (
    DEFAULT_OCR_PROVIDER,
    ensure_runtime_dependencies,
    start_background_dependency_warmup,
)
from app.utils.local_dialog import LocalDialogError, browse_local_path
from app.utils.path_utils import resolve_path


logger = logging.getLogger(__name__)


def _read_version() -> str:
    """Read app version from VERSION file at project root."""
    try:
        candidates = [
            Path(__file__).resolve().parents[2] / "VERSION",
            Path(__file__).resolve().parents[3] / "VERSION",
            Path.cwd() / "VERSION",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "unknown"


_APP_VERSION = _read_version()


def _allowed_cors_origins() -> list[str]:
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    extension_origins = [
        item.strip()
        for item in os.getenv("ALLOWED_EXTENSION_ORIGINS", "").split(",")
        if item.strip()
    ]
    return [*origins, *extension_origins]


def create_app() -> FastAPI:
    app = FastAPI(title="Auto Tool API", version=_APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_cors_origins(),
        allow_origin_regex=r"chrome-extension://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        database.init_db()
        start_background_dependency_warmup(
            include_piper=True,
            include_ocr=True,
            ocr_provider=os.getenv("AUTO_TOOL_OCR_PROVIDER", DEFAULT_OCR_PROVIDER),
            warmup_ocr_models=True,
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=_APP_VERSION)

    @app.get("/api/system/dependencies", response_model=SystemDependencyStatusResponse)
    def system_dependencies() -> SystemDependencyStatusResponse:
        report = ensure_runtime_dependencies(
            auto_install=False,
            include_piper=True,
            include_ocr=True,
            ocr_provider=os.getenv("AUTO_TOOL_OCR_PROVIDER", DEFAULT_OCR_PROVIDER),
            warmup_ocr_models=False,
        )
        return SystemDependencyStatusResponse(
            ffmpeg_path=report.ffmpeg_path,
            ffprobe_path=report.ffprobe_path,
            piper_path=report.piper_path,
            piper_model_path=report.piper_model_path,
            piper_config_path=report.piper_config_path,
            ocr_provider=report.ocr_provider,
            ocr_available=report.ocr_available,
            ocr_message=report.ocr_message,
            warnings=list(report.warnings),
        )

    @app.post("/api/douyin-reup/scan", response_model=DouyinReupScanResponse)
    def scan_douyin_reup_folder(request: DouyinReupScanRequest) -> DouyinReupScanResponse:
        scanner = DouyinFolderScanner()
        try:
            media = scanner.scan_folder(request.source_folder)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể scan thư mục Douyin: {exc}") from exc
        return DouyinReupScanResponse(
            total_files=scanner.total_files,
            valid_videos=len(media),
            invalid_files=scanner.invalid_files,
            media=media,
            errors=scanner.errors,
        )

    @app.get("/api/douyin-reup/presets", response_model=DouyinReupPresetListResponse)
    def list_douyin_reup_presets() -> DouyinReupPresetListResponse:
        return DouyinReupPresetListResponse(presets=DouyinReupPresetService().list_presets())

    @app.get("/api/douyin-reup/presets/{preset_id}")
    def get_douyin_reup_preset(preset_id: str):
        try:
            return DouyinReupPresetService().get_preset(preset_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/douyin-reup/apply-preset", response_model=DouyinApplyPresetResponse)
    def apply_douyin_reup_preset(request: DouyinApplyPresetRequest) -> DouyinApplyPresetResponse:
        service = DouyinReupPresetService()
        try:
            preset = service.get_preset(request.preset_id)
            settings = service.apply_preset(
                request.preset_id,
                current_settings=request.current_settings,
                overrides=request.overrides,
            )
            return DouyinApplyPresetResponse(preset=preset, settings=settings)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc

    @app.post("/api/douyin-reup/recommend-preset", response_model=DouyinPresetRecommendationResponse)
    def recommend_douyin_reup_preset(request: DouyinPresetRecommendationRequest) -> DouyinPresetRecommendationResponse:
        scanner = DouyinFolderScanner()
        try:
            media = scanner.scan_folder(request.source_folder)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        recommendation = _recommend_douyin_preset(media)
        preset = DouyinReupPresetService().get_preset(recommendation["preset_id"])
        return DouyinPresetRecommendationResponse(
            preset_id=preset.id.value,
            preset_name=preset.name,
            reason=recommendation["reason"],
            confidence=recommendation["confidence"],
            signals=recommendation["signals"],
        )

    @app.post("/api/douyin-reup/one-click", response_model=DouyinOneClickBatchResponse)
    def start_douyin_reup_one_click(request: DouyinOneClickBatchRequest) -> DouyinOneClickBatchResponse:
        database.init_db()
        try:
            preset_service = DouyinReupPresetService()
            overrides = _one_click_overrides(request)
            settings = preset_service.apply_preset(request.preset_id, overrides=overrides)
            config = _build_douyin_project_config_from_settings(
                project_name=request.project_name,
                source_folder=request.source_folder,
                output_folder=request.output_folder,
                settings=settings,
            )
            scanner = DouyinFolderScanner()
            media = scanner.scan_folder(config.source_folder)
            total_outputs = _count_douyin_selected(media, config.douyin_reup or DouyinReupSettings(enabled=True))
            if total_outputs <= 0:
                raise ValueError(f"KhÃ´ng tÃ¬m tháº¥y video há»£p lá»‡ trong thÆ° má»¥c Douyin: {config.source_folder}")
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (FileNotFoundError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        project_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        database.create_project(project_id, config.model_dump(mode="json"))
        database.create_job(job_id, project_id, preview_only=False, total_outputs=total_outputs)
        threading.Thread(target=run_douyin_reup_job, args=(job_id,), daemon=True).start()
        return DouyinOneClickBatchResponse(
            project_id=project_id,
            job_id=job_id,
            status="queued",
            preset_id=settings.preset_id or request.preset_id,
            preset_name=settings.preset_name or request.preset_id,
            total_outputs=total_outputs,
        )

    @app.post("/api/douyin-reup/ocr-test", response_model=DouyinOcrTestResponse)
    def test_douyin_hardsub_ocr(request: DouyinOcrTestRequest) -> DouyinOcrTestResponse:
        video_path = Path(request.video_path).expanduser().resolve()
        if not video_path.exists() or not video_path.is_file():
            raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
        try:
            settings = DouyinReupSettings.model_validate(
                {**DouyinReupSettings(enabled=True).model_dump(mode="json"), **(request.settings or {})}
            )
            output_dir = ensure_dir(video_path.parent / "_douyin_ocr_test" / video_path.stem)
            result = HardSubOCRService().extract_hardsub_to_srt(str(video_path), str(output_dir), settings)
            return DouyinOcrTestResponse(
                success=not bool(result.errors),
                result=result.model_dump(mode="json"),
                error="; ".join(result.errors) if result.errors else None,
            )
        except Exception as exc:
            message = str(exc)
            if "PaddleOCR" in message:
                message = (
                    "PaddleOCR is not available yet. Auto Tool will try to install OCR dependencies automatically, "
                    "but paddlepaddle must support the current Python version. Use EasyOCR if PaddleOCR is not supported."
                )
            elif "EasyOCR" in message:
                message = "EasyOCR is not available yet. Auto Tool is installing/downloading OCR dependencies in the background; wait a few minutes and try again."
            return DouyinOcrTestResponse(success=False, error=message)

    @app.post("/api/douyin-reup/process", response_model=DouyinReupProcessResponse)
    def process_douyin_reup_folder(request: DouyinReupProcessRequest) -> DouyinReupProcessResponse:
        database.init_db()
        try:
            config = _build_douyin_project_config(request)
            scanner = DouyinFolderScanner()
            media = scanner.scan_folder(config.source_folder)
            total_outputs = _count_douyin_selected(media, config.douyin_reup or DouyinReupSettings(enabled=True))
            if total_outputs <= 0:
                raise ValueError(f"Không tìm thấy video hợp lệ trong thư mục Douyin: {config.source_folder}")
        except (FileNotFoundError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        project_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        database.create_project(project_id, config.model_dump(mode="json"))
        database.create_job(job_id, project_id, preview_only=False, total_outputs=total_outputs)
        threading.Thread(target=run_douyin_reup_job, args=(job_id,), daemon=True).start()
        return DouyinReupProcessResponse(project_id=project_id, job_id=job_id, status="queued")

    @app.get("/api/subtitle-review/documents", response_model=SubtitleReviewDocumentListResponse)
    def list_subtitle_review_documents(
        project_id: str | None = None,
        job_id: str | None = None,
        status: str | None = None,
    ) -> SubtitleReviewDocumentListResponse:
        try:
            items = SubtitleReviewService().list_documents(project_id=project_id, job_id=job_id, status=status)
            return SubtitleReviewDocumentListResponse(items=items)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/subtitle-review/documents/{document_id}", response_model=SubtitleReviewDocument)
    def get_subtitle_review_document(document_id: str) -> SubtitleReviewDocument:
        try:
            return SubtitleReviewService().get_document(document_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/subtitle-review/documents/{document_id}/lines/{line_index}", response_model=SubtitleLine)
    def update_subtitle_review_line(
        document_id: str,
        line_index: int,
        request: UpdateSubtitleLineRequest,
    ) -> SubtitleLine:
        try:
            return SubtitleReviewService().update_line(document_id, line_index, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/subtitle-review/documents/{document_id}", response_model=SubtitleReviewDocument)
    def save_subtitle_review_document(
        document_id: str,
        request: SaveSubtitleReviewRequest,
    ) -> SubtitleReviewDocument:
        try:
            return SubtitleReviewService().save_document(document_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/subtitle-review/documents/{document_id}/approve", response_model=SubtitleReviewDocument)
    def approve_subtitle_review_document(
        document_id: str,
        request: ApproveSubtitleDocumentRequest,
    ) -> SubtitleReviewDocument:
        try:
            return SubtitleReviewService().approve_document(document_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/api/subtitle-review/documents/{document_id}/quality",
        response_model=SubtitleDocumentQualityReport,
    )
    def get_subtitle_review_quality(document_id: str) -> SubtitleDocumentQualityReport:
        try:
            return SubtitleQualityService().get_quality_report(document_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/subtitle-review/documents/{document_id}/quality/refresh",
        response_model=SubtitleDocumentQualityReport,
    )
    def refresh_subtitle_review_quality(document_id: str) -> SubtitleDocumentQualityReport:
        try:
            return SubtitleQualityService().refresh_quality_report(document_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/subtitle-review/documents/{document_id}/quality/flagged-lines",
        response_model=SubtitleQualityFlaggedLinesResponse,
    )
    def get_subtitle_review_flagged_lines(document_id: str) -> SubtitleQualityFlaggedLinesResponse:
        try:
            return SubtitleQualityFlaggedLinesResponse(
                items=SubtitleQualityService().flagged_lines(document_id)
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/subtitle-review/documents/{document_id}/lines/{line_index}/suggest-rewrite",
        response_model=SubtitleRewriteSuggestionResponse,
    )
    def suggest_subtitle_line_rewrite(
        document_id: str,
        line_index: int,
        request: SubtitleRewriteSuggestionRequest,
    ) -> SubtitleRewriteSuggestionResponse:
        try:
            return SubtitleQualityService().suggest_rewrite(document_id, line_index)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/subtitle-review/documents/{document_id}/lines/{line_index}/rewrite-suggestions",
        response_model=SubtitleRewriteSuggestionsResponse,
    )
    def generate_subtitle_rewrite_suggestions(
        document_id: str,
        line_index: int,
        request: GenerateSubtitleRewriteRequest,
    ) -> SubtitleRewriteSuggestionsResponse:
        try:
            return SubtitleRewriteSuggestionsResponse(
                items=SubtitleRewriteService().generate_suggestions_for_line(document_id, line_index, request)
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/subtitle-review/documents/{document_id}/lines/{line_index}/apply-rewrite",
        response_model=ApplySubtitleRewriteResponse,
    )
    def apply_subtitle_rewrite(
        document_id: str,
        line_index: int,
        request: ApplySubtitleRewriteRequest,
    ) -> ApplySubtitleRewriteResponse:
        try:
            return ApplySubtitleRewriteResponse(
                line=SubtitleRewriteService().apply_suggestion(document_id, line_index, request)
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/subtitle-review/documents/{document_id}/rewrite-flagged-lines",
        response_model=BulkSubtitleRewriteResponse,
    )
    def rewrite_flagged_subtitle_lines(
        document_id: str,
        request: BulkRewriteFlaggedLinesRequest,
    ) -> BulkSubtitleRewriteResponse:
        try:
            return SubtitleRewriteService().generate_suggestions_for_flagged_lines(document_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/subtitle-review/documents/{document_id}/render", response_model=SubtitleReviewRenderResponse)
    def render_subtitle_review_document(
        document_id: str,
        request: RenderSubtitleReviewDocumentRequest,
    ) -> SubtitleReviewRenderResponse:
        document = _get_subtitle_review_or_404(document_id)
        job_id = _queue_subtitle_review_render_job([document.id], request.output_folder, request.settings)
        return SubtitleReviewRenderResponse(job_id=job_id, status="queued")

    @app.post("/api/subtitle-review/render-approved", response_model=SubtitleReviewRenderResponse)
    def render_approved_subtitle_review_documents(
        request: RenderApprovedSubtitleDocumentsRequest,
    ) -> SubtitleReviewRenderResponse:
        documents = SubtitleReviewService().list_documents(
            project_id=request.project_id,
            job_id=request.job_id,
            status="approved",
        )
        if not documents:
            raise HTTPException(status_code=400, detail="No approved subtitle review documents found.")
        job_id = _queue_subtitle_review_render_job([document.id for document in documents], request.output_folder, request.settings)
        return SubtitleReviewRenderResponse(job_id=job_id, status="queued")

    @app.post("/api/system/browse-path", response_model=BrowsePathResponse)
    def browse_path(request: BrowsePathRequest) -> BrowsePathResponse:
        try:
            path = browse_local_path(
                mode=request.mode,
                title=request.title,
                initial_path=request.initial_path,
                extensions=request.extensions,
            )
        except LocalDialogError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return BrowsePathResponse(path=path, cancelled=path is None)

    @app.get("/api/settings", response_model=AppSettings)
    def get_app_settings() -> AppSettings:
        database.init_db()
        return _get_app_settings()

    @app.put("/api/settings", response_model=AppSettings)
    def save_app_settings(settings: AppSettings) -> AppSettings:
        database.init_db()
        saved = database.update_app_settings(settings.model_dump(mode="json"))
        return AppSettings.model_validate(saved)

    @app.post("/api/product-info/import", response_model=ProductInfoImportResponse)
    def import_product_info(request: ProductInfoImportRequest) -> ProductInfoImportResponse:
        if request.save_to_inbox:
            try:
                draft = ProductDraftService().create_from_import_request(
                    CreateProductDraftRequest.model_validate(request.model_dump(mode="json"))
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return ProductInfoImportResponse(
                success=draft.normalized_product is not None
                and not any(issue.severity == "error" for issue in draft.validation_issues),
                product=draft.normalized_product,
                issues=draft.validation_issues,
                source=ProductImportSource(name=draft.source.source_name, url=draft.source.source_url),
                draft=ProductImportDraftSummary(
                    id=draft.id,
                    title=draft.title,
                    status=draft.status.value,
                    confidence_score=draft.confidence_score,
                ),
                import_inbox_url=_import_inbox_url(),
                raw_preview=_raw_import_preview(request),
            )
        result = ProductImportService().import_product_info(request)
        return ProductInfoImportResponse.model_validate(result.model_dump(mode="json"))

    @app.post("/api/projects", response_model=ProjectCreateResponse)
    def create_project(config: ProjectConfig) -> ProjectCreateResponse:
        database.init_db()
        normalized_config = _normalize_config(config)
        project_id = str(uuid.uuid4())
        database.create_project(project_id, normalized_config.model_dump(mode="json"))
        return ProjectCreateResponse(project_id=project_id, status="created")

    @app.get("/api/projects", response_model=ProjectListResponse)
    def list_projects(limit: int = 100, offset: int = 0) -> ProjectListResponse:
        database.init_db()
        projects = database.list_projects(limit=limit, offset=offset)
        return ProjectListResponse(
            items=[
                {
                    "id": project["project_id"],
                    "project_name": project["config"].get("project_name", project["project_id"]),
                    "created_at": project["created_at"],
                }
                for project in projects
            ]
        )

    @app.get("/api/projects/{project_id}", response_model=ProjectDetailResponse)
    def get_project(project_id: str) -> ProjectDetailResponse:
        project = _get_project_or_404(project_id)
        try:
            config = ProjectConfig.model_validate(project["config"])
        except ValidationError as exc:
            raise HTTPException(status_code=500, detail=f"Stored project config is invalid: {exc}") from exc
        return ProjectDetailResponse(
            project_id=project["project_id"],
            status=project["status"],
            config=config,
            created_at=project["created_at"],
            updated_at=project["updated_at"],
        )

    @app.get("/api/product-drafts", response_model=ProductDraftListResponse)
    def list_product_drafts(
        status: str | None = None,
        source_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ProductDraftListResponse:
        try:
            return ProductDraftService().list_drafts(status=status, source_name=source_name, limit=limit, offset=offset)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/product-drafts/clear-archived", response_model=ClearArchivedDraftsResponse)
    def clear_archived_product_drafts() -> ClearArchivedDraftsResponse:
        deleted_count = ProductDraftService().clear_archived()
        return ClearArchivedDraftsResponse(success=True, deleted_count=deleted_count)

    @app.get("/api/product-drafts/{draft_id}", response_model=ProductDraft)
    def get_product_draft(draft_id: str) -> ProductDraft:
        try:
            return ProductDraftService().get_draft(draft_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/product-drafts/{draft_id}", response_model=ProductDraft)
    def update_product_draft(draft_id: str, request: UpdateProductDraftRequest) -> ProductDraft:
        try:
            return ProductDraftService().update_draft(draft_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/product-drafts/{draft_id}/archive", response_model=ProductDraft)
    def archive_product_draft(draft_id: str) -> ProductDraft:
        try:
            return ProductDraftService().archive_draft(draft_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/product-drafts/{draft_id}", response_model=DeleteProductDraftResponse)
    def delete_product_draft(draft_id: str) -> DeleteProductDraftResponse:
        deleted = ProductDraftService().delete_draft(draft_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Product draft not found: {draft_id}")
        return DeleteProductDraftResponse(success=True)

    @app.post(
        "/api/product-drafts/{draft_id}/apply-to-project/{project_id}",
        response_model=ProductDraftApplyResponse,
    )
    def apply_product_draft_to_project(draft_id: str, project_id: str) -> ProductDraftApplyResponse:
        try:
            return ProductDraftService().apply_to_project(draft_id, project_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/product-drafts/{draft_id}/create-project",
        response_model=CreateProjectFromDraftResponse,
    )
    def create_project_from_product_draft(
        draft_id: str,
        request: CreateProjectFromDraftRequest,
    ) -> CreateProjectFromDraftResponse:
        try:
            return ProductDraftService().create_project_from_draft(draft_id, request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/product-drafts/{draft_id}/assets", response_model=ProductAssetListResponse)
    def list_product_draft_assets(draft_id: str) -> ProductAssetListResponse:
        try:
            items = ProductAssetService().list_assets_for_draft(draft_id)
            return ProductAssetListResponse(items=items)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/product-drafts/{draft_id}/assets/import", response_model=ProductAssetsImportResponse)
    def import_product_draft_assets(
        draft_id: str,
        request: ImportAssetsFromDraftRequest,
    ) -> ProductAssetsImportResponse:
        try:
            payload = request.model_copy(update={"draft_id": draft_id})
            items = ProductAssetService().import_assets_from_draft(payload)
            return ProductAssetsImportResponse(success=True, items=items)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/product-drafts/{draft_id}/assets/attach-to-project/{project_id}",
        response_model=AttachDraftAssetsResponse,
    )
    def attach_product_draft_assets_to_project(
        draft_id: str,
        project_id: str,
        request: AttachDraftAssetsRequest,
    ) -> AttachDraftAssetsResponse:
        try:
            items = ProductAssetService().attach_draft_assets_to_project(
                draft_id,
                project_id,
                selected_asset_ids=request.selected_asset_ids,
            )
            return AttachDraftAssetsResponse(
                success=True,
                project_id=project_id,
                attached_count=len(items),
                items=items,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/assets", response_model=ProductAssetListResponse)
    def list_project_assets(project_id: str) -> ProductAssetListResponse:
        try:
            return ProductAssetListResponse(items=ProductAssetService().list_assets_for_project(project_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/product-assets/{asset_id}", response_model=ProductAssetsImportResponse)
    def update_product_asset(asset_id: str, request: UpdateProductAssetRequest) -> ProductAssetsImportResponse:
        try:
            item = ProductAssetService().update_asset(asset_id, request)
            return ProductAssetsImportResponse(success=True, items=[item])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/product-assets/{asset_id}", response_model=ProductAssetsImportResponse)
    def delete_product_asset(asset_id: str) -> ProductAssetsImportResponse:
        try:
            item = ProductAssetService().delete_asset(asset_id)
            return ProductAssetsImportResponse(success=True, items=[item])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/product-assets/{asset_id}/file", response_class=FileResponse)
    def get_product_asset_file(asset_id: str) -> FileResponse:
        asset = ProductAssetService().repository.get(asset_id)
        if not asset or not asset.local_path:
            raise HTTPException(status_code=404, detail=f"Product asset file not found: {asset_id}")
        path = Path(asset.local_path)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail=f"Product asset file not found: {asset_id}")
        return FileResponse(path, media_type=asset.mime_type or "application/octet-stream", filename=asset.filename)

    @app.post("/api/projects/{project_id}/reference-summary", response_model=ReferenceSummaryResponse)
    def generate_reference_summary(project_id: str) -> ReferenceSummaryResponse:
        try:
            summary = ProductReferencePromptService().generate_reference_summary(project_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ReferenceSummaryResponse(success=True, summary=summary)

    @app.post("/api/projects/{project_id}/storyboard", response_model=StoryboardResponse)
    def generate_storyboard(project_id: str, request: StoryboardRequest) -> StoryboardResponse:
        try:
            storyboard = ProductReferencePromptService().generate_storyboard(
                project_id=project_id,
                duration_seconds=request.duration_seconds,
                scene_count=request.scene_count,
                style=request.style,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StoryboardResponse(success=True, storyboard=storyboard)

    @app.post("/api/projects/{project_id}/video-prompt-pack", response_model=VideoPromptPackResponse)
    def generate_video_prompt_pack(
        project_id: str,
        request: VideoPromptPackRequest,
    ) -> VideoPromptPackResponse:
        try:
            prompt_pack, files = ProductReferencePromptService().generate_video_prompt_pack(
                project_id=project_id,
                duration_seconds=request.duration_seconds,
                scene_count=request.scene_count,
                model_hint=request.model_hint,
                style=request.style,
                export_files=True,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return VideoPromptPackResponse(success=True, prompt_pack=prompt_pack, files=files)

    @app.get("/api/projects/{project_id}/latest-script", response_model=LatestScriptResponse)
    def get_latest_script(project_id: str) -> LatestScriptResponse:
        project = _get_project_or_404(project_id)
        script_data = project.get("custom_script") or project.get("latest_script")
        if script_data is None:
            return LatestScriptResponse(script=None)

        try:
            script = ProductVideoScript.model_validate(script_data)
        except ValidationError as exc:
            raise HTTPException(status_code=500, detail=f"Stored script is invalid: {exc}") from exc
        return LatestScriptResponse(script=script)

    @app.put("/api/projects/{project_id}/script", response_model=LatestScriptResponse)
    def save_project_script(project_id: str, script: ProductVideoScript) -> LatestScriptResponse:
        _get_project_or_404(project_id)
        database.update_project_custom_script(project_id, script.model_dump(mode="json"))
        return LatestScriptResponse(script=script)

    @app.post("/api/projects/{project_id}/safety-check", response_model=SafetyCheckResult)
    def check_project_safety(project_id: str) -> SafetyCheckResult:
        project = _get_project_or_404(project_id)
        try:
            config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        except ValidationError as exc:
            return _validation_error_safety_result(exc)
        return SafetyGuardService().check_before_render(config)

    @app.put("/api/projects/{project_id}/product-info", response_model=UpdateProjectProductInfoResponse)
    def update_project_product_info(
        project_id: str,
        request: UpdateProjectProductInfoRequest,
    ) -> UpdateProjectProductInfoResponse:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        product = _prepare_product_info_for_project(request.product)
        industry = (
            IndustrySettings(preset_id=product.industry_preset_id)
            if product.industry_preset_id
            else config.industry
        )
        updated_config = config.model_copy(
            update={
                "product": to_project_product_info(product),
                "industry": industry,
            }
        )
        updated = database.update_project_config(project_id, updated_config.model_dump(mode="json"))
        if not updated:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return UpdateProjectProductInfoResponse(
            success=True,
            project_id=project_id,
            product=product,
            updated_config=updated_config,
        )

    @app.post("/api/projects/{project_id}/scan", response_model=ScanResponse)
    def scan_project(project_id: str) -> ScanResponse:
        project = _get_project_or_404(project_id)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        folder = Path(config.source_folder)
        if not folder.exists() or not folder.is_dir():
            raise HTTPException(status_code=400, detail=f"Source folder does not exist: {folder}")

        candidate_files = [
            path
            for path in folder.rglob("*")
            if path.is_file() and path.suffix.lower() in MediaScanner.supported_extensions
        ]
        try:
            media = MediaScanner().scan_folder(config.source_folder)
        except FFmpegError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ScanResponse(
            total_files=len(candidate_files),
            valid_videos=len(media),
            invalid_files=max(0, len(candidate_files) - len(media)),
            media=media,
        )

    @app.post("/api/projects/{project_id}/analyze-segments", response_model=SegmentScoringResponse)
    def analyze_project_segments(project_id: str) -> SegmentScoringResponse:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        try:
            media = MediaScanner().scan_folder(config.source_folder)
            if not media:
                raise ValueError(
                    f"Không tìm thấy video hợp lệ nào trong: {config.source_folder}\n"
                    "  → Hãy bỏ file video (.mp4, .mov, .mkv) vào thư mục nguồn và thử lại."
                )
            segments = Segmenter().create_segments(media, config.effects.cut_intensity)
            if not segments:
                raise ValueError(
                    "Không tạo được đoạn cắt nào từ video nguồn. "
                    "Video có thể quá ngắn hoặc không đọc được."
                )
            scored_segments = SegmentScorer().score_segments(segments)
        except FFmpegError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Không tìm thấy FFmpeg. Hãy cài FFmpeg và thêm vào PATH trước khi render video. Chi tiết: {exc}",
            ) from exc
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        report = build_scoring_report(scored_segments)
        report_path = ensure_dir(config.output_folder) / "segment_scoring_report.json"
        write_json(report_path, report)
        return SegmentScoringResponse(
            total_segments=report["total_segments"],
            usable_segments=report["usable_segments"],
            rejected_segments=report["rejected_segments"],
            average_score=report["average_score"],
            rejection_summary=report["rejection_summary"],
            report_path=str(report_path),
        )

    @app.get("/api/projects/{project_id}/source-media", response_model=SourceMediaResponse)
    def get_project_source_media(project_id: str) -> SourceMediaResponse:
        _get_project_or_404(project_id)
        try:
            media_items = MediaManagerService().get_source_media_items(project_id)
        except (FFmpegError, FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        summary = build_source_media_summary(media_items, [])
        segment_reviews = database.list_segment_reviews(project_id)
        summary = summary.model_copy(
            update={
                "excluded_segments": sum(
                    1 for item in segment_reviews if item.get("review_status") in {"excluded", "bad"}
                ),
                "favorite_segments": sum(
                    1 for item in segment_reviews if item.get("review_status") == "favorite"
                ),
            }
        )
        return SourceMediaResponse(
            summary=summary,
            items=media_items,
        )

    @app.put(
        "/api/projects/{project_id}/source-media/review",
        response_model=UpdateSourceMediaReviewResponse,
    )
    def update_project_source_media_review(
        project_id: str,
        request: UpdateSourceMediaReviewRequest,
    ) -> UpdateSourceMediaReviewResponse:
        _get_project_or_404(project_id)
        try:
            item = MediaManagerService().update_media_review(
                project_id=project_id,
                media_path=request.media_path,
                review_status=request.review_status,
                user_note=request.user_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UpdateSourceMediaReviewResponse(success=True, item=item)

    @app.get("/api/projects/{project_id}/segments", response_model=SegmentReviewResponse)
    def get_project_segments(
        project_id: str,
        source_path: str | None = Query(default=None),
        status: str | None = Query(default=None),
        min_score: float | None = Query(default=None),
        tag: str | None = Query(default=None),
    ) -> SegmentReviewResponse:
        _get_project_or_404(project_id)
        try:
            items = SegmentReviewService().get_segment_review_items(
                project_id=project_id,
                source_path=source_path,
                status=status,
                min_score=min_score,
                tag=tag,
            )
        except (FFmpegError, FileNotFoundError, NotADirectoryError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SegmentReviewResponse(items=items)

    @app.put(
        "/api/projects/{project_id}/segments/{segment_id}/review",
        response_model=UpdateSegmentReviewResponse,
    )
    def update_project_segment_review(
        project_id: str,
        segment_id: str,
        request: UpdateSegmentReviewRequest,
    ) -> UpdateSegmentReviewResponse:
        _get_project_or_404(project_id)
        try:
            item = SegmentReviewService().update_segment_review(
                project_id=project_id,
                segment_id=segment_id,
                review_status=request.review_status,
                user_note=request.user_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UpdateSegmentReviewResponse(success=True, item=item)

    @app.post(
        "/api/projects/{project_id}/segments/bulk-review",
        response_model=BulkSegmentReviewResponse,
    )
    def bulk_update_project_segment_review(
        project_id: str,
        request: BulkSegmentReviewRequest,
    ) -> BulkSegmentReviewResponse:
        _get_project_or_404(project_id)
        try:
            updated_count = SegmentReviewService().bulk_update_segment_review(
                project_id=project_id,
                segment_ids=request.segment_ids,
                review_status=request.review_status,
                user_note=request.user_note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return BulkSegmentReviewResponse(success=True, updated_count=updated_count)

    @app.post("/api/projects/{project_id}/render", response_model=RenderResponse)
    def render_project_endpoint(project_id: str, request: RenderRequest) -> RenderResponse:
        project = _get_project_or_404(project_id)
        try:
            config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        except ValidationError as exc:
            safety_result = _validation_error_safety_result(exc)
            raise HTTPException(
                status_code=400,
                detail=_safety_error_detail(safety_result),
            ) from exc
        safety_result = SafetyGuardService().check_before_render(config)
        if safety_result.errors_count:
            raise HTTPException(
                status_code=400,
                detail=_safety_error_detail(safety_result),
            )
        # Validate output folder writability before queuing job
        try:
            out_dir = Path(config.output_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            test_file = out_dir / ".write_check"
            test_file.touch()
            test_file.unlink(missing_ok=True)
        except PermissionError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Không có quyền ghi vào thư mục đầu ra: {config.output_folder}\n"
                    "  → Hãy kiểm tra quyền truy cập thư mục hoặc chọn thư mục khác."
                ),
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể tạo thư mục đầu ra: {config.output_folder} — {exc}",
            ) from exc
        total_outputs = 1 if request.preview_only else config.render.output_count
        job_id = str(uuid.uuid4())
        database.create_job(job_id, project_id, request.preview_only, total_outputs)
        database.add_job_log(job_id, "info", "Tác vụ render đã được đưa vào hàng đợi.")

        for issue in safety_result.issues:
            if issue.severity == "warning":
                database.add_job_log(job_id, "warning", f"Safety check: {issue.message}")

        thread = threading.Thread(target=run_render_job, args=(job_id,), daemon=True)
        thread.start()
        return RenderResponse(job_id=job_id, status="queued")

    @app.get("/api/projects/{project_id}/outputs/review", response_model=OutputReviewResponse)
    def review_project_outputs(project_id: str) -> OutputReviewResponse:
        _get_project_or_404(project_id)
        try:
            service = OutputQualityReviewService()
            scores = service.analyze_project_outputs(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return OutputReviewResponse(
            summary=service.build_summary(scores),
            outputs=build_review_rows(project_id, scores),
        )

    @app.post("/api/projects/{project_id}/crop-safety/analyze", response_model=None)
    def analyze_project_crop_safety(project_id: str) -> dict[str, Any]:
        _get_project_or_404(project_id)
        report_path = _latest_crop_safety_report_path(project_id)
        if report_path is None:
            return {
                "success": False,
                "error": "No timeline available. Render preview or build timelines first.",
            }
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail=f"Could not read crop safety report: {exc}") from exc
        return {
            "success": True,
            "total_clips_analyzed": report.get("total_clips_analyzed", 0),
            "average_crop_safety_score": report.get("average_crop_safety_score", 0),
            "fallback_to_blur_background": report.get("fallback_to_blur_background", 0),
            "warnings_summary": report.get("warnings_summary", {}),
            "report_path": str(report_path),
        }

    @app.get("/api/projects/{project_id}/cache/summary", response_model=None)
    def get_project_cache_summary(project_id: str) -> dict[str, Any]:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        return CacheService.for_project(config).summary()

    @app.post("/api/projects/{project_id}/cache/clear", response_model=None)
    def clear_project_cache(project_id: str) -> dict[str, Any]:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        CacheService.for_project(config).clear()
        return {"success": True, "message": "Đã xoá cache dự án."}

    @app.put(
        "/api/projects/{project_id}/outputs/{output_index}/review",
        response_model=UpdateOutputReviewResponse,
    )
    def update_output_review(
        project_id: str,
        output_index: int,
        request: UpdateOutputReviewRequest,
    ) -> UpdateOutputReviewResponse:
        _get_project_or_404(project_id)
        if output_index <= 0:
            raise HTTPException(status_code=400, detail="output_index must be greater than 0.")
        database.update_output_review(
            project_id=project_id,
            output_index=output_index,
            review_status=request.review_status.value,
            user_note=request.user_note,
        )
        return UpdateOutputReviewResponse(
            success=True,
            output_index=output_index,
            review_status=request.review_status,
        )

    @app.get("/api/projects/{project_id}/content", response_model=ContentItemsResponse)
    def get_project_content(project_id: str) -> ContentItemsResponse:
        _get_project_or_404(project_id)
        try:
            items = ContentService().get_content_items(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ContentItemsResponse(summary=build_content_summary(items), items=items)

    @app.put(
        "/api/projects/{project_id}/content/{output_index}",
        response_model=UpdateContentItemResponse,
    )
    def update_project_content_item(
        project_id: str,
        output_index: int,
        request: UpdateContentItemRequest,
    ) -> UpdateContentItemResponse:
        _get_project_or_404(project_id)
        try:
            item = ContentService().update_content_item(
                project_id,
                output_index,
                request.model_dump(exclude_none=True, mode="json"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UpdateContentItemResponse(success=True, item=item)

    @app.post(
        "/api/projects/{project_id}/content/{output_index}/mark-copied",
        response_model=UpdateContentItemResponse,
    )
    def mark_project_content_copied(project_id: str, output_index: int) -> UpdateContentItemResponse:
        _get_project_or_404(project_id)
        try:
            item = ContentService().mark_copied(project_id, output_index)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UpdateContentItemResponse(success=True, item=item)

    @app.post(
        "/api/projects/{project_id}/content/{output_index}/mark-posted",
        response_model=UpdateContentItemResponse,
    )
    def mark_project_content_posted(
        project_id: str,
        output_index: int,
        request: MarkPostedRequest | None = None,
    ) -> UpdateContentItemResponse:
        _get_project_or_404(project_id)
        try:
            item = ContentService().mark_posted(
                project_id,
                output_index,
                platform=request.platform if request else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return UpdateContentItemResponse(success=True, item=item)

    @app.post("/api/projects/{project_id}/content/export", response_model=ContentExportResponse)
    def export_project_content(project_id: str, request: ExportContentRequest) -> ContentExportResponse:
        _get_project_or_404(project_id)
        try:
            files = ContentService().export_content(project_id, request.formats)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ContentExportResponse(
            success=True,
            files=[ContentExportFile(format=format_name, path=path) for format_name, path in files.items()],
        )

    @app.post("/api/projects/{project_id}/rerender", response_model=RerenderResponse)
    def rerender_project_outputs(project_id: str, request: RerenderRequest) -> RerenderResponse:
        _get_project_or_404(project_id)
        try:
            rerender_outputs = RerenderService().resolve_output_indexes(
                project_id=project_id,
                mode=request.mode,
                output_indexes=request.output_indexes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not rerender_outputs:
            raise HTTPException(status_code=400, detail="No outputs matched this rerender request.")

        job_id = str(uuid.uuid4())
        database.create_job(job_id, project_id, preview_only=False, total_outputs=len(rerender_outputs))
        database.add_job_log(job_id, "info", f"Tác vụ render lại đã được đưa vào hàng đợi cho video: {rerender_outputs}")
        thread = threading.Thread(
            target=run_rerender_job,
            args=(job_id, request.model_dump(mode="json"), rerender_outputs),
            daemon=True,
        )
        thread.start()
        return RerenderResponse(job_id=job_id, status="queued", rerender_outputs=rerender_outputs)

    @app.get("/api/script-variants/styles", response_model=ScriptVariantStylesResponse)
    def get_script_variant_styles() -> ScriptVariantStylesResponse:
        styles = [
            ScriptVariantStyleItem.model_validate(style.model_dump(mode="json"))
            for style in list_variant_styles()
        ]
        return ScriptVariantStylesResponse(styles=styles)

    @app.get("/api/tts/providers", response_model=TTSProvidersResponse)
    def get_tts_providers() -> TTSProvidersResponse:
        providers = [
            TTSProviderItem.model_validate(provider.model_dump(mode="json"))
            for provider in list_tts_providers()
        ]
        return TTSProvidersResponse(providers=providers)

    @app.get("/api/visual-styles", response_model=VisualStylePresetsResponse)
    def get_visual_styles() -> VisualStylePresetsResponse:
        presets = [
            VisualStylePresetItem.model_validate(preset.model_dump(mode="json"))
            for preset in list_visual_style_presets()
        ]
        return VisualStylePresetsResponse(presets=presets)

    @app.post("/api/visual-styles/preview", response_model=VisualStylePreviewResponse)
    def preview_visual_style(request: VisualStylePreviewRequest) -> VisualStylePreviewResponse:
        try:
            path = VisualStyleService().preview_style(
                preset_id=request.preset_id,
                sample_text=request.sample_text,
                resolution=request.resolution,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return VisualStylePreviewResponse(
            success=True,
            preview_image_path=path,
            preview_image_url=f"/api/files/image?path={quote(path)}",
        )

    @app.put("/api/projects/{project_id}/visual-style", response_model=UpdateProjectVisualStyleResponse)
    def update_project_visual_style(
        project_id: str,
        request: UpdateProjectVisualStyleRequest,
    ) -> UpdateProjectVisualStyleResponse:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        preset = get_visual_style_preset(request.preset_id)
        visual_style = config.visual_style.model_copy(update={"preset_id": preset.id, "custom_overrides": None})
        updated_config = config.model_copy(update={"visual_style": visual_style})
        updated = database.update_project_config(project_id, updated_config.model_dump(mode="json"))
        if not updated:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return UpdateProjectVisualStyleResponse(
            success=True,
            visual_style=visual_style.model_dump(mode="json"),
        )

    @app.get("/api/industry-presets", response_model=IndustryPresetsResponse)
    def get_industry_presets() -> IndustryPresetsResponse:
        return IndustryPresetsResponse(presets=IndustryPresetService().list_presets())

    @app.get("/api/industry-presets/{preset_id}", response_model=IndustryPreset)
    def get_industry_preset_detail(preset_id: str) -> IndustryPreset:
        return IndustryPresetService().get_preset(preset_id)

    @app.put("/api/projects/{project_id}/industry-preset", response_model=ApplyIndustryPresetResponse)
    def apply_project_industry_preset(
        project_id: str,
        request: ApplyIndustryPresetRequest,
    ) -> ApplyIndustryPresetResponse:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
        updated_config = IndustryPresetService().apply_preset_to_config(
            config,
            request.preset_id,
            apply_visual_style=request.apply_visual_style,
            apply_timeline=request.apply_timeline,
            apply_script_variation=request.apply_script_variation,
            apply_tts_voice=request.apply_tts_voice,
            apply_edit_strength=request.apply_edit_strength,
        )
        updated = database.update_project_config(project_id, updated_config.model_dump(mode="json"))
        if not updated:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        preset_id = updated_config.industry.preset_id if updated_config.industry else request.preset_id
        return ApplyIndustryPresetResponse(
            success=True,
            project_id=project_id,
            preset_id=preset_id or request.preset_id,
            updated_config=updated_config,
        )

    @app.post("/api/tts/google-cloud/voices", response_model=TTSVoicesResponse)
    def get_google_cloud_tts_voices(request: TTSVoicesRequest) -> TTSVoicesResponse:
        settings = _get_app_settings()
        try:
            voices = list_google_cloud_voices(
                api_key=request.api_key or settings.google_tts_api_key,
                language_code=request.language_code,
                credentials_json_path=request.credentials_json_path or settings.google_tts_credentials_json_path,
                access_token=request.access_token or settings.google_tts_access_token,
            )
        except TTSProviderError as exc:
            logger.warning("Could not load Google Cloud TTS voices: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TTSVoicesResponse(
            voices=[TTSVoiceItem.model_validate(voice.model_dump(mode="json")) for voice in voices]
        )

    @app.post(
        "/api/projects/{project_id}/generate-script-variants",
        response_model=GenerateScriptVariantsResponse,
    )
    def generate_project_script_variants(
        project_id: str,
        request: GenerateScriptVariantsRequest,
    ) -> GenerateScriptVariantsResponse:
        project = _get_project_or_404(project_id)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        output_count = request.output_count or config.render.output_count
        timeline_template_id = request.timeline_template_id or config.timeline.template_id
        try:
            generator = ScriptVariantGenerator()
            generator.generate_variants(config, output_count, timeline_template_id)
            report_path = generator.write_report(config.output_folder, config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return GenerateScriptVariantsResponse(
            total_variants=len(generator.results),
            variants=[
                ScriptVariantSummaryItem(
                    output_index=variant.output_index,
                    variant_style_id=variant.variant_style_id,
                    hook=variant.hook,
                )
                for variant in generator.results
            ],
            report_path=report_path,
        )

    @app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
    def get_job(job_id: str) -> JobStatusResponse:
        job = _get_job_or_404(job_id)
        logs = database.get_job_logs(job_id)
        return JobStatusResponse(
            job_id=job["job_id"],
            status=job["status"],
            current_step=job["current_step"],
            progress=job["progress"],
            total_outputs=job["total_outputs"],
            completed_outputs=job["completed_outputs"],
            failed_outputs=job["failed_outputs"],
            logs=logs,
            cache_summary=job.get("results", {}).get("cache_summary"),
        )

    @app.get("/api/jobs/{job_id}/results", response_model=JobResultsResponse)
    def get_job_results(job_id: str) -> JobResultsResponse:
        job = _get_job_or_404(job_id)
        return JobResultsResponse(outputs=job["results"].get("outputs", []))

    @app.get("/api/douyin-reup/jobs/{job_id}/results", response_model=DouyinReupJobResultsResponse)
    def get_douyin_reup_job_results(job_id: str) -> DouyinReupJobResultsResponse:
        job = _get_job_or_404(job_id)
        payload = job.get("results") or {}
        return DouyinReupJobResultsResponse(
            summary=payload.get("summary"),
            outputs=payload.get("outputs", []),
        )

    @app.post("/api/final-output-qa/check", response_model=FinalOutputQACheckResponse)
    def check_final_output(request: FinalOutputQACheckRequest) -> FinalOutputQACheckResponse:
        report = FinalOutputQAService().run_qa_for_output(
            request.output_video_path,
            request.platform_target,
            ass_path=request.ass_path,
            overlay_path=request.overlay_path,
            subtitle_expected=request.subtitle_expected,
            audio_expected=request.audio_expected,
        )
        return FinalOutputQACheckResponse(report=report)

    @app.post("/api/final-output-qa/jobs/{job_id}/check", response_model=FinalOutputQAJobResponse)
    def check_final_outputs_for_job(
        job_id: str,
        request: FinalOutputQAJobRequest,
    ) -> FinalOutputQAJobResponse:
        try:
            reports = FinalOutputQAService().run_qa_for_job(job_id, request.platform_target)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FinalOutputQAJobResponse(
            reports=reports,
            summary=build_final_qa_summary(reports, request.platform_target),
        )

    @app.post("/api/douyin-reup/jobs/{job_id}/export-pack", response_model=PlatformExportPackResponse)
    def create_douyin_export_pack(
        job_id: str,
        request: CreateExportPackRequest,
    ) -> PlatformExportPackResponse:
        try:
            pack = ExportPackService().create_export_pack_for_job(
                job_id,
                request.platform_target,
                request.output_dir,
                copy_videos=request.copy_videos,
                include_subtitles=request.include_subtitles,
                include_logs=request.include_logs,
                include_captions=request.include_captions,
                include_posting_checklist=request.include_posting_checklist,
                output_indexes=request.output_indexes,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return PlatformExportPackResponse(export_pack=pack)

    @app.get("/api/douyin-reup/jobs/{job_id}/export-pack", response_model=PlatformExportPackResponse)
    def get_douyin_export_pack(job_id: str) -> PlatformExportPackResponse:
        try:
            return PlatformExportPackResponse(export_pack=ExportPackService().get_export_pack_for_job(job_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/final-output-qa/report", response_model=None)
    def get_final_output_qa_report(path: str = Query(...)) -> FileResponse:
        report_path = Path(path).expanduser().resolve()
        if not report_path.exists() or not report_path.is_file() or report_path.suffix.lower() != ".json":
            raise HTTPException(status_code=404, detail=f"QA report not found: {report_path}")
        if not database.is_known_job_artifact_path(str(report_path)):
            raise HTTPException(status_code=403, detail="QA report path is not registered as a job artifact.")
        return FileResponse(report_path, media_type="application/json", filename=report_path.name)

    @app.post("/api/douyin-reup/jobs/{job_id}/export-pack/open", response_model=dict)
    def open_douyin_export_pack(job_id: str) -> dict:
        try:
            path = ExportPackService().open_export_pack_folder(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"success": True, "path": path}

    @app.post("/api/douyin-reup/jobs/{job_id}/retry-failed", response_model=DouyinRetryFailedResponse)
    def retry_failed_douyin_reup_outputs(job_id: str, request: DouyinRetryFailedRequest) -> DouyinRetryFailedResponse:
        original_job = _get_job_or_404(job_id)
        failed_outputs = [
            output
            for output in (original_job.get("results") or {}).get("outputs", [])
            if isinstance(output, dict)
            and (
                output.get("status") == "failed"
                or (isinstance(output.get("final_output_qa"), dict) and output["final_output_qa"].get("status") == "failed")
            )
            and output.get("source_video")
        ]
        if not failed_outputs:
            raise HTTPException(status_code=400, detail="Không có video failed hợp lệ để retry.")
        retry_job_id = _queue_douyin_retry_failed_job(
            original_job_id=job_id,
            failed_outputs=failed_outputs,
            retry_steps=set(request.retry_steps or ["asr", "translation", "render"]),
            settings_override=request.settings,
        )
        return DouyinRetryFailedResponse(job_id=retry_job_id, status="queued", retry_outputs=len(failed_outputs))

    @app.post("/api/douyin-reup/jobs/{job_id}/retry-with-preset", response_model=DouyinRetryFailedResponse)
    def retry_douyin_reup_outputs_with_preset(
        job_id: str,
        request: DouyinRetryWithPresetRequest,
    ) -> DouyinRetryFailedResponse:
        original_job = _get_job_or_404(job_id)
        failed_outputs = [
            output
            for output in (original_job.get("results") or {}).get("outputs", [])
            if isinstance(output, dict)
            and (
                output.get("status") == "failed"
                or (isinstance(output.get("final_output_qa"), dict) and output["final_output_qa"].get("status") == "failed")
            )
            and output.get("source_video")
        ]
        failed_outputs = _filter_douyin_outputs_by_ids(failed_outputs, request.video_ids)
        if not failed_outputs:
            raise HTTPException(status_code=400, detail="KhÃ´ng cÃ³ video failed há»£p lá»‡ Ä‘á»ƒ retry.")

        project = database.get_project(original_job["project_id"])
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {original_job['project_id']}")
        try:
            config = ProjectConfig.model_validate(project["config"])
            base_settings = config.douyin_reup or DouyinReupSettings(enabled=True)
            merged_overrides = {**(request.settings or {}), **(request.advanced_overrides or {})}
            retry_settings = DouyinReupPresetService().apply_preset(
                request.preset_id,
                current_settings=base_settings,
                overrides=merged_overrides,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc

        retry_job_id = _queue_douyin_retry_failed_job(
            original_job_id=job_id,
            failed_outputs=failed_outputs,
            retry_steps=set(request.retry_steps or ["asr", "translation", "render"]),
            settings_override=retry_settings.model_dump(mode="json"),
        )
        return DouyinRetryFailedResponse(job_id=retry_job_id, status="queued", retry_outputs=len(failed_outputs))

    @app.get("/api/files/video", response_model=None)
    def get_video_file(path: str = Query(...)) -> FileResponse:
        video_path = Path(path).expanduser().resolve()
        if not video_path.exists() or not video_path.is_file():
            raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
        if video_path.suffix.lower() != ".mp4":
            raise HTTPException(status_code=400, detail="Only .mp4 preview files are supported.")
        if not database.is_known_output_path(str(video_path)):
            raise HTTPException(status_code=403, detail="Video path is not registered as a render output.")
        return FileResponse(video_path, media_type="video/mp4", filename=video_path.name)

    @app.get("/api/files/image", response_model=None)
    def get_image_file(path: str = Query(...)) -> FileResponse:
        image_path = Path(path).expanduser().resolve()
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(status_code=400, detail="Only PNG/JPG image preview files are supported.")
        try:
            image_path.relative_to(app_data_dir().resolve())
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Image path is not a registered Auto Tool preview asset.") from exc
        media_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(image_path, media_type=media_type, filename=image_path.name)

    @app.get("/api/files/thumbnail", response_model=None)
    def get_thumbnail_file(path: str = Query(...)) -> FileResponse:
        image_path = Path(path).expanduser().resolve()
        if not image_path.exists() or not image_path.is_file():
            raise HTTPException(status_code=404, detail=f"Thumbnail not found: {image_path}")
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise HTTPException(status_code=400, detail="Only JPG/PNG thumbnail files are supported.")
        if "thumbnails" not in [part.lower() for part in image_path.parts]:
            raise HTTPException(status_code=403, detail="Path is not an Auto Tool thumbnail.")
        media_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(image_path, media_type=media_type, filename=image_path.name)

    @app.get("/api/presets", response_model=list[PresetItem])
    def get_presets() -> list[PresetItem]:
        return [PresetItem.model_validate(preset) for preset in get_default_presets()]

    @app.get("/api/timeline-templates", response_model=TimelineTemplatesResponse)
    def get_timeline_templates() -> TimelineTemplatesResponse:
        templates = [
            TimelineTemplateItem(
                id=template.id,
                name=template.name,
                description=template.description,
            )
            for template in list_timeline_templates()
        ]
        return TimelineTemplatesResponse(templates=templates)

    _mount_frontend(app)
    return app


def run_render_job(job_id: str) -> None:
    database.init_db()
    job = database.get_job(job_id)
    if not job:
        return

    project = database.get_project(job["project_id"])
    if not project:
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            error=f"Project not found: {job['project_id']}",
        )
        return

    def progress_callback(payload: dict[str, Any]) -> None:
        database.update_job(
            job_id,
            status="running",
            current_step=payload.get("current_step", "running"),
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        custom_script = None
        if project.get("custom_script"):
            custom_script = ProductVideoScript.model_validate(project["custom_script"])
        summary = render_project(
            config,
            preview_only=job["preview_only"],
            custom_script=custom_script,
            project_id=job["project_id"],
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        _save_latest_script_from_summary(job["project_id"], summary, log_callback)
        status = "completed" if summary["failed_outputs"] == 0 else "completed_with_errors"
        database.update_job(
            job_id,
            status=status,
            current_step="completed",
            progress=100,
            total_outputs=summary["requested_outputs"],
            completed_outputs=summary["successful_outputs"],
            failed_outputs=summary["failed_outputs"],
            output_folder=summary["output_folder"],
            results_json=json.dumps(
                {
                    "outputs": summary["outputs"],
                    "cache_summary": summary.get("cache_summary"),
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def run_douyin_reup_job(job_id: str) -> None:
    database.init_db()
    job = database.get_job(job_id)
    if not job:
        return

    project = database.get_project(job["project_id"])
    if not project:
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            error=f"Project not found: {job['project_id']}",
        )
        return

    def progress_callback(payload: dict[str, Any]) -> None:
        database.update_job(
            job_id,
            status="running",
            current_step=payload.get("current_step", "running"),
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        summary = DouyinReupService().process_folder(
            config,
            project_id=job["project_id"],
            job_id=job_id,
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        status = "completed" if summary.get("failed_outputs", 0) == 0 else "completed_with_errors"
        database.update_job(
            job_id,
            status=status,
            current_step="completed",
            progress=100,
            total_outputs=int(summary.get("processed_outputs") or job["total_outputs"]),
            completed_outputs=int(summary.get("successful_outputs") or 0),
            failed_outputs=int(summary.get("failed_outputs") or 0),
            output_folder=summary.get("output_folder"),
            results_json=json.dumps(
                {
                    "summary": summary,
                    "outputs": summary.get("outputs", []),
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def run_douyin_reup_retry_job(
    job_id: str,
    original_job_id: str,
    failed_outputs: list[dict[str, Any]],
    retry_steps: set[str],
    settings_override: dict[str, Any],
) -> None:
    database.init_db()
    job = database.get_job(job_id)
    original_job = database.get_job(original_job_id)
    if not job or not original_job:
        return

    project = database.get_project(original_job["project_id"])
    if not project:
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            error=f"Project not found: {original_job['project_id']}",
        )
        return

    def progress_callback(payload: dict[str, Any]) -> None:
        database.update_job(
            job_id,
            status="running",
            current_step=f"retry_{payload.get('current_step', 'running')}",
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="retry_starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        base_settings = config.douyin_reup or DouyinReupSettings(enabled=True)
        merged_settings = DouyinReupSettings.model_validate(
            {**base_settings.model_dump(mode="json"), **(settings_override or {})}
        )
        selected_paths = [str(output["source_video"]) for output in failed_outputs if output.get("source_video")]
        merged_settings = merged_settings.model_copy(
            update={
                "enabled": True,
                "process_mode": "selected",
                "selected_video_paths": selected_paths,
                "max_videos": None,
            }
        )
        config = config.model_copy(update={"douyin_reup": merged_settings})
        summary = DouyinReupService().process_folder(
            config,
            project_id=job["project_id"],
            job_id=job_id,
            retry_cache=build_retry_cache(failed_outputs),
            retry_steps=retry_steps,
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        status = "completed" if summary.get("failed_outputs", 0) == 0 else "completed_with_errors"
        database.update_job(
            job_id,
            status=status,
            current_step="completed",
            progress=100,
            total_outputs=int(summary.get("processed_outputs") or job["total_outputs"]),
            completed_outputs=int(summary.get("successful_outputs") or 0),
            failed_outputs=int(summary.get("failed_outputs") or 0),
            output_folder=summary.get("output_folder"),
            results_json=json.dumps(
                {
                    "summary": summary,
                    "outputs": summary.get("outputs", []),
                    "retry_of_job_id": original_job_id,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def run_subtitle_review_render_job(
    job_id: str,
    document_ids: list[str],
    output_folder: str,
    settings_payload: dict[str, Any],
) -> None:
    database.init_db()
    job = database.get_job(job_id)
    if not job:
        return

    total = len(document_ids)
    output_root = ensure_dir(Path(output_folder) / f"subtitle-review-render-{uuid.uuid4().hex[:8]}")
    outputs: list[dict[str, Any]] = []
    failed = 0
    completed = 0
    settings = DouyinReupSettings.model_validate(settings_payload)
    pipeline = DouyinRenderPipeline()

    try:
        database.update_job(job_id, status="running", current_step="render_approved_subtitles", progress=1)
        for index, document_id in enumerate(document_ids, start=1):
            try:
                document_dir = ensure_dir(output_root / f"video_{index:03d}")
                log_path = document_dir / f"video_{index:03d}_log.json"
                result = pipeline.render_from_review_document(document_id, settings, str(document_dir))
                qa_report = FinalOutputQAService().run_qa_for_output(
                    str(result["path"]),
                    PlatformTarget.tiktok,
                    job_id=job_id,
                    project_id=job.get("project_id"),
                    video_id=f"video_{index:03d}",
                    ass_path=result.get("corrected_ass_file") or result.get("subtitle_ass_file"),
                    overlay_path=result.get("overlay_file"),
                    subtitle_expected=settings.burn_subtitle,
                    audio_expected=settings.keep_original_audio or settings.add_bgm,
                    overlay_expected=settings.add_overlay,
                    report_path=str(document_dir / f"video_{index:03d}_final_qa.json"),
                )
                qa_summary = {
                    "status": qa_report.status,
                    "score": qa_report.score,
                    "report_path": qa_report.report_path,
                    "issues": [issue.model_dump(mode="json") for issue in qa_report.issues],
                }
                write_json(
                    log_path,
                    {
                        "index": index,
                        "input_document": document_id,
                        "status": "success",
                        "steps": {"render": "ok"},
                        "final_output_qa": qa_summary,
                        "warnings": result.get("warnings") or [],
                        "errors": result.get("errors") or [],
                    },
                )
                outputs.append(
                    {
                        "index": index,
                        "path": result["path"],
                        "status": "success",
                        "source_video": result.get("source_video"),
                        "source_srt_file": result.get("source_srt_file"),
                        "translated_srt_file": result.get("translated_srt_file"),
                        "corrected_srt_file": result.get("corrected_srt_file"),
                        "subtitle_ass_file": result.get("subtitle_ass_file"),
                        "corrected_ass_file": result.get("corrected_ass_file"),
                        "overlay_file": result.get("overlay_file"),
                        "bgm_file": result.get("bgm_file"),
                        "log_file": str(log_path),
                        "duration": result.get("duration"),
                        "warnings": result.get("warnings") or [],
                        "errors": result.get("errors") or [],
                        "subtitle_review_document_id": document_id,
                        "final_output_qa": qa_summary,
                    }
                )
                completed += 1
            except Exception as exc:
                failed += 1
                document_dir = ensure_dir(output_root / f"video_{index:03d}")
                log_path = document_dir / f"video_{index:03d}_log.json"
                write_json(
                    log_path,
                    {
                        "index": index,
                        "input_document": document_id,
                        "status": "failed",
                        "steps": {"render": "failed"},
                        "failed_step": "render",
                        "error_message": str(exc),
                        "can_retry": True,
                        "warnings": [],
                        "errors": [str(exc)],
                    },
                )
                outputs.append(
                    {
                        "index": index,
                        "path": "",
                        "status": "failed",
                        "source_video": "",
                        "log_file": str(log_path),
                        "failed_step": "render",
                        "error_message": str(exc),
                        "can_retry": True,
                        "warnings": [],
                        "errors": [str(exc)],
                        "subtitle_review_document_id": document_id,
                    }
                )
                database.add_job_log(job_id, "error", f"Subtitle review render failed for {document_id}: {exc}")

            database.update_job(
                job_id,
                status="running",
                current_step=f"subtitle_review_render_{index}",
                progress=max(1, min(99, int(index / max(total, 1) * 95))),
                total_outputs=total,
                completed_outputs=completed,
                failed_outputs=failed,
            )

        status = "completed" if failed == 0 else "completed_with_errors"
        summary = {
            "output_folder": str(output_root),
            "processed_outputs": len(outputs),
            "successful_outputs": completed,
            "failed_outputs": failed,
            "outputs": outputs,
            "final_output_qa": _final_qa_summary_from_outputs(outputs),
        }
        write_json(output_root / "subtitle_review_render_summary.json", summary)
        database.update_job(
            job_id,
            status=status,
            current_step="completed",
            progress=100,
            total_outputs=total,
            completed_outputs=completed,
            failed_outputs=failed,
            output_folder=str(output_root),
            results_json=json.dumps({"summary": summary, "outputs": outputs}, ensure_ascii=False),
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=total,
            error=str(exc),
        )


def run_rerender_job(job_id: str, request_payload: dict[str, Any], rerender_outputs: list[int]) -> None:
    database.init_db()
    job = database.get_job(job_id)
    if not job:
        return

    project = database.get_project(job["project_id"])
    if not project:
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            error=f"Project not found: {job['project_id']}",
        )
        return

    def progress_callback(payload: dict[str, Any]) -> None:
        database.update_job(
            job_id,
            status="running",
            current_step=payload.get("current_step", "running"),
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        summary = RerenderService().rerender_outputs(
            project_id=job["project_id"],
            config=config,
            output_indexes=rerender_outputs,
            mode=str(request_payload.get("mode") or "selected"),
            reuse_script=bool(request_payload.get("reuse_script", True)),
            reuse_timeline=bool(request_payload.get("reuse_timeline", False)),
            reuse_settings=bool(request_payload.get("reuse_settings", True)),
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        _save_latest_script_from_summary(job["project_id"], summary, log_callback)
        status = "completed" if summary["failed_outputs"] == 0 else "completed_with_errors"
        database.update_job(
            job_id,
            status=status,
            current_step="completed",
            progress=100,
            total_outputs=summary["requested_outputs"],
            completed_outputs=summary["successful_outputs"],
            failed_outputs=summary["failed_outputs"],
            output_folder=summary["output_folder"],
            results_json=json.dumps(
                {
                    "outputs": summary["outputs"],
                    "cache_summary": summary.get("cache_summary"),
                },
                ensure_ascii=False,
            ),
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def _save_latest_script_from_summary(
    project_id: str,
    summary: dict[str, Any],
    log_callback,
) -> None:
    for output in summary.get("outputs", []):
        script_file = output.get("script_file")
        if not script_file:
            continue

        try:
            payload = json.loads(Path(script_file).read_text(encoding="utf-8"))
            script = ProductVideoScript.model_validate(payload)
            database.update_project_latest_script(project_id, script.model_dump(mode="json"))
            log_callback("info", f"Đã lưu kịch bản mới nhất từ {script_file}")
            return
        except Exception as exc:
            log_callback("warning", f"Không thể lưu kịch bản mới nhất từ {script_file}: {exc}")


def _get_app_settings() -> AppSettings:
    return AppSettings.model_validate(database.get_app_settings() or {})


def _build_douyin_project_config(request: DouyinReupProcessRequest) -> ProjectConfig:
    return _build_douyin_project_config_from_settings(
        project_name=request.project_name,
        source_folder=request.source_folder,
        output_folder=request.output_folder,
        settings=request.settings,
    )


def _build_douyin_project_config_from_settings(
    *,
    project_name: str,
    source_folder: str,
    output_folder: str,
    settings: DouyinReupSettings,
) -> ProjectConfig:
    base_dir = Path.cwd()
    settings = _normalize_douyin_settings(settings.model_copy(update={"enabled": True}), base_dir)
    source_folder = str(resolve_path(source_folder, base_dir, must_exist=True))
    output_folder = str(resolve_path(output_folder, base_dir))
    return ProjectConfig.model_validate(
        {
            "project_name": project_name.strip(),
            "source_folder": source_folder,
            "output_folder": output_folder,
            "product": {
                "name": "Douyin Reup",
                "brand": "",
                "description": "Xử lý video Douyin local với subtitle dịch sang tiếng Việt.",
                "features": ["Dịch subtitle", "Thêm overlay", "Trộn nhạc nền"],
                "cta": "Xem video",
            },
            "render": {
                "output_count": settings.max_videos or 1,
                "duration": 8,
                "aspect_ratio": "9:16",
                "resolution": settings.resolution,
                "fps": settings.fps,
            },
            "effects": {
                "cut_intensity": 0,
                "speed_variation": 0,
                "grain": 0,
                "zoom_motion": 0,
                "overlay_height": 22,
                "subtitle_size": 54,
            },
            "ai": {
                "text_model": "gemini-3.1-flash-lite",
                "tone": "subtitle_translator",
                "language": settings.target_language,
                "gemini_api_keys": [],
            },
            "music": {
                "enabled": False,
                "volume": 0.12,
                "fade_in": 0.5,
                "fade_out": 0.8,
                "duck_under_voice": False,
            },
            "visual_style": {"preset_id": settings.visual_style_preset_id},
            "douyin_reup": settings.model_dump(mode="json"),
        }
    )


def _one_click_overrides(request: DouyinOneClickBatchRequest) -> dict[str, Any]:
    process_mode = "all" if request.process_mode == "all_videos" else request.process_mode
    overrides: dict[str, Any] = {
        "process_mode": process_mode,
        "selected_video_paths": request.selected_video_paths,
    }
    if request.max_videos is not None:
        overrides["max_videos"] = request.max_videos
    if request.bgm_folder is not None:
        overrides["music_folder"] = request.bgm_folder
    if request.visual_style_preset_id:
        overrides["visual_style_preset_id"] = request.visual_style_preset_id
    if request.review_subtitles_before_render is not None:
        overrides["review_subtitles_before_render"] = request.review_subtitles_before_render
    if request.auto_render_after_translation is not None:
        overrides["auto_render_after_translation"] = request.auto_render_after_translation
    overrides.update(request.advanced_overrides or {})
    return overrides


def _normalize_douyin_settings(settings: DouyinReupSettings, base_dir: Path) -> DouyinReupSettings:
    updates: dict[str, Any] = {}
    if settings.music_folder:
        updates["music_folder"] = str(resolve_path(settings.music_folder, base_dir, must_exist=True))
    if settings.selected_video_paths:
        updates["selected_video_paths"] = [
            str(resolve_path(path, base_dir, must_exist=True)) for path in settings.selected_video_paths
        ]
    return settings.model_copy(update=updates) if updates else settings


def _count_douyin_selected(videos: list[Any], settings: DouyinReupSettings) -> int:
    selected = videos
    if settings.process_mode == "selected":
        selected_paths = {str(Path(path).expanduser().resolve()).lower() for path in settings.selected_video_paths}
        selected = [video for video in videos if str(Path(video.path).expanduser().resolve()).lower() in selected_paths]
    if settings.max_videos:
        selected = selected[: settings.max_videos]
    return len(selected)


def _recommend_douyin_preset(videos: list[Any]) -> dict[str, Any]:
    total = len(videos)
    if total <= 0:
        return {
            "preset_id": "safe_review",
            "reason": "No valid video found; safe review is the least risky default.",
            "confidence": 0.4,
            "signals": {"total": 0},
        }

    with_subtitle = len([video for video in videos if getattr(video, "sidecar_srt_path", None) or getattr(video, "embedded_subtitle_found", False)])
    with_audio = len([video for video in videos if getattr(video, "has_audio", False)])
    no_audio = total - with_audio
    subtitle_ratio = with_subtitle / total
    audio_ratio = with_audio / total
    no_audio_ratio = no_audio / total
    signals = {
        "total": total,
        "with_subtitle": with_subtitle,
        "with_audio": with_audio,
        "no_audio": no_audio,
        "subtitle_ratio": round(subtitle_ratio, 3),
        "audio_ratio": round(audio_ratio, 3),
    }
    if no_audio_ratio >= 0.5:
        return {
            "preset_id": "ocr_priority",
            "reason": "Many videos have no audio, so visible subtitle OCR is the safer first fallback.",
            "confidence": 0.82,
            "signals": signals,
        }
    if subtitle_ratio >= 0.6:
        return {
            "preset_id": "clean_subtitle_only",
            "reason": "Most videos already have subtitle sources, so a clean subtitle pass should be enough.",
            "confidence": 0.76,
            "signals": signals,
        }
    if audio_ratio >= 0.7:
        return {
            "preset_id": "voice_priority",
            "reason": "Most videos have audio, so ASR-first processing is a practical default.",
            "confidence": 0.72,
            "signals": signals,
        }
    return {
        "preset_id": "safe_review",
        "reason": "Input signals are mixed; safe review keeps manual QA before render.",
        "confidence": 0.66,
        "signals": signals,
    }


def _final_qa_summary_from_outputs(outputs: list[dict[str, Any]]) -> dict[str, int | float]:
    reports = [output.get("final_output_qa") for output in outputs if output.get("final_output_qa")]
    return {
        "total_checked": len(reports),
        "passed": sum(1 for report in reports if report.get("status") == "passed"),
        "passed_with_warnings": sum(1 for report in reports if report.get("status") == "passed_with_warnings"),
        "failed": sum(1 for report in reports if report.get("status") == "failed"),
        "average_score": round(sum(float(report.get("score") or 0) for report in reports) / len(reports), 4) if reports else 0.0,
    }


def _filter_douyin_outputs_by_ids(outputs: list[dict[str, Any]], video_ids: list[str]) -> list[dict[str, Any]]:
    if not video_ids:
        return outputs
    requested = {str(item).strip().lower() for item in video_ids if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for output in outputs:
        source_video = str(output.get("source_video") or "")
        keys = {
            str(output.get("index") or "").lower(),
            f"video_{int(output.get('index') or 0):03d}" if output.get("index") else "",
            source_video.lower(),
            Path(source_video).name.lower() if source_video else "",
        }
        if requested.intersection(keys):
            filtered.append(output)
    return filtered


def _apply_app_settings(config: ProjectConfig) -> ProjectConfig:
    settings = _get_app_settings()
    ai_updates: dict[str, Any] = {}
    if settings.gemini_api_keys:
        ai_updates["gemini_api_keys"] = settings.gemini_api_keys

    tts_updates: dict[str, Any] = {}
    if settings.google_tts_api_key:
        tts_updates["api_key"] = settings.google_tts_api_key
    if settings.google_tts_credentials_json_path:
        tts_updates["credentials_json_path"] = settings.google_tts_credentials_json_path
    if settings.google_tts_access_token:
        tts_updates["access_token"] = settings.google_tts_access_token

    updates: dict[str, Any] = {}
    if ai_updates:
        updates["ai"] = config.ai.model_copy(update=ai_updates)
    if tts_updates:
        updates["tts"] = config.tts.model_copy(update=tts_updates)
    return config.model_copy(update=updates) if updates else config


def _validation_error_safety_result(exc: ValidationError) -> SafetyCheckResult:
    issues: list[SafetyIssue] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", [])) or "config"
        issues.append(
            SafetyIssue(
                severity="error",
                category="invalid_project_config",
                field=loc,
                message=f"Project config không hợp lệ ở '{loc}': {error.get('msg', 'Validation error')}",
                suggestion="Sửa lại thông tin sản phẩm hoặc tạo lại project từ form.",
            )
        )
    return build_safety_result(issues)


def _safety_error_detail(safety_result: SafetyCheckResult) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Product info safety check failed",
        "issues": [issue.model_dump(mode="json") for issue in safety_result.issues],
    }


def _raw_import_preview(request: ProductInfoImportRequest) -> str | None:
    text = request.file_content or request.raw_text
    if not text and request.structured_data:
        text = json.dumps(request.structured_data, ensure_ascii=False)
    if not text and request.file_path:
        text = request.file_path
    if not text and request.source_url:
        text = request.source_url
    return text[:500] if text else None


def _import_inbox_url() -> str:
    frontend_url = os.getenv("AUTO_TOOL_FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
    return f"{frontend_url or 'http://localhost:5173'}/import-inbox"


def _get_subtitle_review_or_404(document_id: str) -> SubtitleReviewDocument:
    try:
        return SubtitleReviewService().get_document(document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _queue_subtitle_review_render_job(
    document_ids: list[str],
    output_folder: str,
    settings: DouyinReupSettings,
) -> str:
    if not document_ids:
        raise HTTPException(status_code=400, detail="No subtitle review documents selected.")
    documents = [_get_subtitle_review_or_404(document_id) for document_id in document_ids]
    not_approved = [document.id for document in documents if document.status.value != "approved"]
    if not_approved:
        raise HTTPException(status_code=400, detail=f"Documents must be approved before render: {', '.join(not_approved)}")
    project_id = documents[0].project_id or f"subtitle-review:{documents[0].id}"
    job_id = str(uuid.uuid4())
    database.create_job(job_id, project_id, preview_only=False, total_outputs=len(documents))
    threading.Thread(
        target=run_subtitle_review_render_job,
        args=(job_id, document_ids, output_folder, settings.model_dump(mode="json")),
        daemon=True,
    ).start()
    return job_id


def _queue_douyin_retry_failed_job(
    *,
    original_job_id: str,
    failed_outputs: list[dict[str, Any]],
    retry_steps: set[str],
    settings_override: dict[str, Any],
) -> str:
    original_job = _get_job_or_404(original_job_id)
    retry_job_id = str(uuid.uuid4())
    database.create_job(retry_job_id, original_job["project_id"], preview_only=False, total_outputs=len(failed_outputs))
    threading.Thread(
        target=run_douyin_reup_retry_job,
        args=(retry_job_id, original_job_id, failed_outputs, retry_steps, settings_override),
        daemon=True,
    ).start()
    return retry_job_id


def _prepare_product_info_for_project(product: ProductInfoNormalized) -> ProductInfoNormalized:
    normalized = ProductNormalizer().normalize(product)
    industry_id = normalized.industry_preset_id or suggest_industry_preset(normalized)
    industry = get_industry_preset(industry_id)
    normalized = ProductNormalizer().normalize(
        normalized.model_copy(
            update={
                "industry_preset_id": industry.id,
                "hashtag_suggestions": normalized.hashtag_suggestions or industry.hashtag_suggestions,
            }
        )
    )
    issues = ProductValidator().validate(normalized)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        detail = "; ".join(issue.message for issue in errors)
        raise HTTPException(status_code=400, detail=detail)
    warnings = [*normalized.warnings, *[issue.message for issue in issues if issue.severity == "warning"]]
    missing_fields = [issue.field for issue in issues if issue.severity == "error"]
    return normalized.model_copy(
        update={
            "warnings": _dedupe_text(warnings),
            "missing_fields": _dedupe_text(missing_fields),
        }
    )


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).strip().split())
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _normalize_config(config: ProjectConfig) -> ProjectConfig:
    base_dir = Path.cwd()
    music_updates: dict[str, str] = {}
    if config.music.source_folder:
        music_updates["source_folder"] = str(resolve_path(config.music.source_folder, base_dir, must_exist=True))
    if config.music.source_file:
        music_updates["source_file"] = str(resolve_path(config.music.source_file, base_dir, must_exist=True))
    music = config.music.model_copy(update=music_updates) if music_updates else config.music
    visual_style_updates: dict[str, str] = {}
    if config.visual_style.overlay_mode == "custom" and config.visual_style.custom_overlay_path:
        visual_style_updates["custom_overlay_path"] = str(
            resolve_path(config.visual_style.custom_overlay_path, base_dir, must_exist=True)
        )
    visual_style = (
        config.visual_style.model_copy(update=visual_style_updates)
        if visual_style_updates
        else config.visual_style
    )
    douyin_reup = config.douyin_reup
    if douyin_reup:
        douyin_reup = _normalize_douyin_settings(douyin_reup, base_dir)

    return config.model_copy(
        update={
            "source_folder": str(resolve_path(config.source_folder, base_dir, must_exist=True)),
            "output_folder": str(resolve_path(config.output_folder, base_dir)),
            "music": music,
            "visual_style": visual_style,
            "douyin_reup": douyin_reup,
        }
    )


def _get_project_or_404(project_id: str) -> dict[str, Any]:
    database.init_db()
    project = database.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


def _get_job_or_404(job_id: str) -> dict[str, Any]:
    database.init_db()
    job = database.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


def _latest_crop_safety_report_path(project_id: str) -> Path | None:
    jobs = database.get_project_jobs(project_id, include_preview=True)
    for job in reversed(jobs):
        output_folder = job.get("output_folder")
        if output_folder:
            report_path = Path(output_folder) / "crop_safety_report.json"
            if report_path.exists():
                return report_path
        for output in reversed(job.get("results", {}).get("outputs", [])):
            timeline_file = output.get("timeline_file") if isinstance(output, dict) else None
            if not timeline_file:
                continue
            report_path = Path(timeline_file).parent / "crop_safety_report.json"
            if report_path.exists():
                return report_path
    return None


def _mount_frontend(app: FastAPI) -> None:
    dist_dir = frontend_dist_dir()
    index_file = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_file.exists():
        return

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def serve_frontend(full_path: str):
        requested = (dist_dir / full_path).resolve()
        try:
            requested.relative_to(dist_dir)
        except ValueError:
            requested = index_file

        if requested.is_file() and requested.name != "index.html":
            return FileResponse(requested)
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
