from __future__ import annotations

import json
import logging
import os
import inspect
import random
import threading
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import database
from app.adapters.ffmpeg_adapter import FFmpegError, probe_media_duration
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.content_manager.content_schema import build_content_summary
from app.modules.content_manager.content_service import ContentService
from app.modules.cache.cache_service import CacheService
from app.modules.music_selector.music_selector import MusicSelector
from app.modules.content_safety.safety_guard_service import SafetyGuardService
from app.modules.content_safety.safety_schema import SafetyCheckResult, SafetyIssue, build_safety_result
from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.bgm_mixer import SUPPORTED_BGM_EXTENSIONS
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_reup_service import DouyinReupService, build_retry_cache
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.douyin_downloader import (
    DouyinDownloaderCloseResponse,
    DouyinDownloaderDownloadRequest,
    DouyinDownloaderHistoryResponse,
    DouyinDownloaderJobActionResponse,
    DouyinDownloaderJobResponse,
    DouyinDownloaderOpenRequest,
    DouyinDownloaderScanRequest,
    DouyinDownloaderService,
    DouyinDownloaderStatusResponse,
)
from app.modules.douyin_downloader.downloader_service import DouyinDownloaderError
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
from app.modules.queue_control import (
    QueueActionRequest,
    QueueActionResult,
    QueueControlAction,
    QueueControlService,
    QueueItemPriority,
    QueuePriorityService,
    QueueRetryService,
    QueueSettings,
    QueueStateResponse,
    QueueStateService,
    QueueWatchdogService,
    ResourceGuardService,
    ResourceStatusResponse,
)
from app.modules.render_worker.render_worker import render_project
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.segmenter.segmenter import Segmenter
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_variants.variant_registry import list_variant_styles
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_reup_service import SilentReupService
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan
from app.modules.silent_visual_tagging.visual_tag_repository import VisualTagRepository
from app.modules.silent_visual_tagging.visual_tag_schema import (
    TAG_CATEGORY_BY_NAME,
    VISUAL_TAG_VOCABULARY,
    SilentVisualTaggingMetadata,
    SegmentVisualTagResult,
    UpdateSegmentVisualTagsRequest,
    VideoVisualTagReport,
    VisualTag,
    VisualTagCategory,
)
from app.modules.silent_visual_tagging.visual_tag_service import VisualTagService
from app.modules.silent_caption_templates.caption_template_service import (
    SilentCaptionTemplateService,
    list_industries as list_silent_caption_industries,
)
from app.modules.source_media_manager.media_manager_service import MediaManagerService, build_source_media_summary
from app.modules.source_media_manager.segment_review_service import SegmentReviewService
from app.modules.source_media import (
    SourceFolderScanRequest,
    SourceFolderScanResult,
    SourceMediaRepository,
    SourceMediaScanner,
    SourceMediaSelectionRequest,
    SourceMediaSelectionResult,
    SourceMediaSelectionService,
)
from app.modules.timeline_templates.template_registry import list_timeline_templates
from app.modules.tts.tts_manager import TTSManager, list_tts_providers
from app.modules.tts.tts_schema import TTSSettings
from app.modules.tts.providers.google_cloud_tts_provider import list_google_cloud_voices
from app.modules.tts.providers.base import TTSProviderError
from app.modules.visual_style.style_registry import get_visual_style_preset, list_visual_style_presets
from app.modules.visual_style.custom_overlay_asset import select_custom_overlay_asset
from app.modules.visual_style.visual_style_service import VisualStyleService
from app.local_app import (
    LocalAppConfig,
    LocalConfigService,
    LocalDesktopActionResponse,
    LocalDesktopService,
    LocalFrontendStatusResponse,
    LocalPathRequest,
    LocalPathsService,
    LocalRecentPaths,
    LocalSystemCheckResponse,
    LocalSystemService,
    StaticFrontendService,
)
from app.local_app.data_management import (
    BackupListResponse,
    BackupRequest,
    BackupResult,
    BackupService,
    CleanupRequest,
    CleanupResult,
    CleanupService,
    RestoreRequest,
    RestoreResult,
    RestoreService,
    StorageUsageApiResponse,
    StorageUsageService,
)
from app.local_app.data_management.data_management_schema import BackupInspectRequest, BackupInspectResult
from app.modules.job_recovery import (
    JobCheckpointService,
    JobRecoveryActionResponse,
    JobRecoveryCandidatesResponse,
    JobRecoveryCandidatesData,
    JobRecoveryJobData,
    JobRecoveryJobResponse,
    JobRecoveryService,
    JobReconciliationService,
    JobResumeService,
    JobRunStatus,
    RecoverableStep,
    ResumeJobRequest,
    ResumeJobResult,
)
from app.presets import get_default_presets
from app.utils.env_loader import load_local_env
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
    MusicLibraryResponse,
    MusicLibraryTrack,
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
    ConfigRequirementCheckRequest,
    ConfigRequirementCheckResponse,
    ConfigRequirementIssue,
    ProjectCreateResponse,
    ProjectDetailResponse,
    RenderRequest,
    RenderResponse,
    RerenderRequest,
    RerenderResponse,
    ScanResponse,
    SegmentReviewResponse,
    SegmentScoringResponse,
    SilentReupDetectRequest,
    SilentReupDetectResponse,
    SilentCaptionIndustriesResponse,
    SilentCaptionRegenerateRequest,
    SilentCaptionTemplateListResponse,
    SilentReupOneClickRequest,
    SilentReupPlanRequest,
    SilentReupPlanResponse,
    SilentReupRenderRequest,
    SilentReupRenderResponse,
    SilentReupReviewDocumentResponse,
    SilentVisualTagReportResponse,
    SilentVisualTagVocabularyResponse,
    ScriptVariantStyleItem,
    ScriptVariantStylesResponse,
    ScriptVariantSummaryItem,
    SourceMediaResponse,
    StoryboardRequest,
    StoryboardResponse,
    SystemDependencyStatusResponse,
    TTSProviderItem,
    TTSProvidersResponse,
    TTSPreviewRequest,
    TTSPreviewResponse,
    TTSVoiceItem,
    TTSVoicesRequest,
    TTSVoicesResponse,
    TimelineTemplateItem,
    TimelineTemplatesResponse,
    MarkPostedRequest,
    UpdateCheckResponse,
    UpdateDownloadResponse,
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
from app.utils.app_paths import app_data_dir
from app.utils.dependency_manager import (
    DEFAULT_OCR_PROVIDER,
    ensure_runtime_dependencies,
    start_background_dependency_warmup,
)
from app.utils.local_dialog import LocalDialogError, browse_local_path
from app.utils.path_utils import resolve_path
from app.utils.updater import get_cached_update_info, download_and_prepare_update
from app.version import APP_VERSION


logger = logging.getLogger(__name__)
_SILENT_PLAN_STORE: dict[str, dict[str, Any]] = {}


_APP_VERSION = APP_VERSION


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
    local_config_service = LocalConfigService()
    local_paths_service = LocalPathsService(local_config_service)
    local_system_service = LocalSystemService(local_config_service, local_paths_service)
    local_desktop_service = LocalDesktopService(local_config_service, local_paths_service)
    static_frontend_service = StaticFrontendService(local_config_service)
    storage_usage_service = StorageUsageService()
    backup_service = BackupService()
    restore_service = RestoreService(backup_service=backup_service)
    cleanup_service = CleanupService()
    job_checkpoint_service = JobCheckpointService()
    job_recovery_service = JobRecoveryService(job_checkpoint_service)
    job_reconciliation_service = JobReconciliationService()
    job_resume_service = JobResumeService(
        reconciliation_service=job_reconciliation_service,
        checkpoint_service=job_checkpoint_service,
    )
    queue_state_service = QueueStateService()
    queue_control_service = QueueControlService(queue_state_service)
    queue_priority_service = QueuePriorityService(queue_state_service)
    queue_retry_service = QueueRetryService(queue_state_service)
    queue_watchdog_service = QueueWatchdogService(queue_state_service)
    douyin_downloader_service = DouyinDownloaderService()
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
        recoverable = job_recovery_service.mark_interrupted_jobs_on_startup()
        if recoverable:
            logger.warning("Marked %s interrupted job(s) as recoverable.", len(recoverable))
        local_config = local_config_service.load_config()
        local_paths_service.ensure_folder(local_config.default_output_folder)
        start_background_dependency_warmup(
            include_piper=True,
            include_ocr=True,
            ocr_provider=os.getenv("AUTO_TOOL_OCR_PROVIDER", DEFAULT_OCR_PROVIDER),
            warmup_ocr_models=True,
        )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=_APP_VERSION,
            capabilities={
                "douyin_reup": True,
                "douyin_downloader": True,
                "silent_immersive_mode": True,
                "translation": _has_gemini_key(None),
                "google_cloud_tts": _has_google_tts_auth(),
            },
            recoverable_jobs_count=job_recovery_service.count_recoverable_jobs(),
        )

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

    @app.get("/api/system/update-check", response_model=UpdateCheckResponse)
    def system_update_check(force: bool = False) -> UpdateCheckResponse:
        info = get_cached_update_info(force=force)
        return UpdateCheckResponse(
            has_update=info.has_update,
            current_version=info.current_version,
            latest_version=info.latest_version,
            download_url=info.download_url,
            html_url=info.html_url,
            release_name=info.release_name,
            release_notes=info.release_notes,
            error=info.error,
        )

    @app.post("/api/system/update-download", response_model=UpdateDownloadResponse)
    def system_update_download() -> UpdateDownloadResponse:
        info = get_cached_update_info(force=False)
        if not info.has_update:
            raise HTTPException(status_code=400, detail="Không có phiên bản mới để tải.")
        res = download_and_prepare_update(info)
        if not res.success:
            raise HTTPException(status_code=500, detail=res.error or "Tải bản cập nhật thất bại.")
        return UpdateDownloadResponse(
            success=True,
            extract_dir=res.extract_dir,
            updater_script=res.updater_script,
            message="Đã tải và chuẩn bị bản cập nhật. Vui lòng đóng ứng dụng để tự động cập nhật.",
        )

    @app.get("/api/local-app/config", response_model=LocalAppConfig)
    def get_local_app_config() -> LocalAppConfig:
        return local_config_service.load_config()

    @app.put("/api/local-app/config", response_model=LocalAppConfig)
    def save_local_app_config(config: LocalAppConfig) -> LocalAppConfig:
        try:
            local_paths_service.ensure_folder(config.default_output_folder)
            return local_config_service.save_config(config)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"Cannot prepare local app folders: {exc}") from exc

    @app.get("/api/local-app/system-check", response_model=LocalSystemCheckResponse)
    def local_app_system_check() -> LocalSystemCheckResponse:
        return local_system_service.check_system()

    @app.get("/api/local-app/frontend-status", response_model=LocalFrontendStatusResponse)
    def local_app_frontend_status() -> LocalFrontendStatusResponse:
        return static_frontend_service.build_api_response()

    @app.get("/api/local-app/recent-paths", response_model=LocalRecentPaths)
    def get_local_app_recent_paths() -> LocalRecentPaths:
        return local_paths_service.get_recent_paths()

    @app.post("/api/local-app/recent-paths/source", response_model=LocalRecentPaths)
    def add_local_app_source_path(request: LocalPathRequest) -> LocalRecentPaths:
        return local_paths_service.add_recent_path("source", request.path)

    @app.post("/api/local-app/recent-paths/output", response_model=LocalRecentPaths)
    def add_local_app_output_path(request: LocalPathRequest) -> LocalRecentPaths:
        return local_paths_service.add_recent_path("output", request.path)

    @app.post("/api/local-app/recent-paths/music", response_model=LocalRecentPaths)
    def add_local_app_music_path(request: LocalPathRequest) -> LocalRecentPaths:
        return local_paths_service.add_recent_path("music", request.path)

    @app.post("/api/local-app/open-folder", response_model=LocalDesktopActionResponse)
    def open_local_app_folder(request: LocalPathRequest) -> LocalDesktopActionResponse:
        try:
            path = local_desktop_service.open_folder(request.path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Cannot open folder: {exc}") from exc
        return LocalDesktopActionResponse(success=True, path=str(path), message="Folder opened.")

    @app.post("/api/local-app/reveal-file", response_model=LocalDesktopActionResponse)
    def reveal_local_app_file(request: LocalPathRequest) -> LocalDesktopActionResponse:
        try:
            path = local_desktop_service.reveal_file(request.path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Cannot reveal file: {exc}") from exc
        return LocalDesktopActionResponse(success=True, path=str(path), message="File revealed.")

    @app.get("/api/local-app/storage-usage", response_model=StorageUsageApiResponse)
    def local_app_storage_usage() -> StorageUsageApiResponse:
        report = storage_usage_service.build_report()
        return StorageUsageApiResponse(success=True, data=report, warnings=report.warnings, errors=[])

    @app.post("/api/local-app/backup", response_model=BackupResult)
    def local_app_create_backup(request: BackupRequest) -> BackupResult:
        return backup_service.create_backup(request)

    @app.get("/api/local-app/backups", response_model=BackupListResponse)
    def local_app_list_backups() -> BackupListResponse:
        return backup_service.list_backups()

    @app.post("/api/local-app/backup/inspect", response_model=BackupInspectResult)
    def local_app_inspect_backup(request: BackupInspectRequest) -> BackupInspectResult:
        return restore_service.inspect_backup(request.backup_path)

    @app.post("/api/local-app/restore", response_model=RestoreResult)
    def local_app_restore_backup(request: RestoreRequest) -> RestoreResult:
        return restore_service.restore_backup(request)

    @app.post("/api/local-app/cleanup/preview", response_model=CleanupResult)
    def local_app_cleanup_preview(request: CleanupRequest) -> CleanupResult:
        return cleanup_service.preview_cleanup(request)

    @app.post("/api/local-app/cleanup/run", response_model=CleanupResult)
    def local_app_cleanup_run(request: CleanupRequest) -> CleanupResult:
        return cleanup_service.run_cleanup(request)

    @app.get("/api/job-recovery/candidates", response_model=JobRecoveryCandidatesResponse)
    def get_job_recovery_candidates() -> JobRecoveryCandidatesResponse:
        items = job_recovery_service.find_recovery_candidates()
        return JobRecoveryCandidatesResponse(success=True, data=JobRecoveryCandidatesData(items=items))

    @app.get("/api/job-recovery/jobs/{job_id}", response_model=JobRecoveryJobResponse)
    def get_job_recovery_job(job_id: str) -> JobRecoveryJobResponse:
        try:
            candidate = job_recovery_service.inspect_job_recovery(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        checkpoint = job_checkpoint_service.load_job_checkpoint(job_id)
        videos = job_checkpoint_service.load_video_checkpoints(job_id)
        job = database.get_job(job_id)
        reconciliation = None
        try:
            reconciliation = job_reconciliation_service.reconcile_job_outputs(job_id)
        except LookupError:
            reconciliation = None
        return JobRecoveryJobResponse(
            success=True,
            data=JobRecoveryJobData(
                candidate=candidate,
                checkpoint=checkpoint,
                video_checkpoints=videos,
                reconciliation=reconciliation,
                job=job,
            ),
        )

    @app.post("/api/job-recovery/jobs/{job_id}/reconcile", response_model=JobRecoveryActionResponse)
    def reconcile_recovery_job(job_id: str) -> JobRecoveryActionResponse:
        try:
            data = job_reconciliation_service.reconcile_job_outputs(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JobRecoveryActionResponse(success=True, data=data)

    @app.post("/api/job-recovery/jobs/{job_id}/resume", response_model=ResumeJobResult)
    def resume_recovery_job(job_id: str, request: ResumeJobRequest) -> ResumeJobResult:
        request = request.model_copy(update={"job_id": job_id})
        result = job_resume_service.resume_job(request)
        if not result.success:
            raise HTTPException(status_code=400, detail="; ".join(result.errors) or "Không thể resume job.")
        if result.new_job_id:
            original_job = _get_job_or_404(job_id)
            retry_outputs = _douyin_resume_outputs(result.resume_plan or {})
            if _job_looks_douyin(original_job) and retry_outputs:
                threading.Thread(
                    target=_run_resume_thread,
                    args=(
                        job_id,
                        job_resume_service,
                        run_douyin_reup_retry_job,
                        result.new_job_id,
                        job_id,
                        retry_outputs,
                        {"asr", "translation", "render"},
                        {},
                    ),
                    daemon=True,
                ).start()
            elif _job_looks_douyin(original_job):
                threading.Thread(
                    target=_run_resume_thread,
                    args=(job_id, job_resume_service, run_douyin_reup_job, result.new_job_id),
                    daemon=True,
                ).start()
            else:
                threading.Thread(
                    target=_run_resume_thread,
                    args=(job_id, job_resume_service, run_render_job, result.new_job_id),
                    daemon=True,
                ).start()
        else:
            job_resume_service.release_resume_lock(job_id)
        return result

    @app.post("/api/job-recovery/jobs/{job_id}/mark-cancelled", response_model=JobRecoveryActionResponse)
    def mark_recovery_job_cancelled(job_id: str) -> JobRecoveryActionResponse:
        try:
            candidate = job_recovery_service.mark_cancelled(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JobRecoveryActionResponse(success=True, data={"candidate": candidate.model_dump(mode="json")})

    @app.post("/api/job-recovery/jobs/{job_id}/cleanup-lock", response_model=JobRecoveryActionResponse)
    def cleanup_recovery_job_lock(job_id: str) -> JobRecoveryActionResponse:
        was_locked = job_resume_service.locks.is_job_locked(job_id)
        job_resume_service.locks.release_job_lock(job_id)
        return JobRecoveryActionResponse(success=True, data={"was_locked": was_locked, "lock_released": True})

    def _start_resume_job_for_queue(job_id: str, resume_mode: str) -> ResumeJobResult:
        request = ResumeJobRequest(
            job_id=job_id,
            resume_mode=resume_mode,  # type: ignore[arg-type]
            skip_completed_outputs=True,
            do_not_overwrite_existing_outputs=True,
        )
        result = job_resume_service.resume_job(request)
        if not result.success:
            return result
        if result.new_job_id:
            original_job = _get_job_or_404(job_id)
            retry_outputs = _douyin_resume_outputs(result.resume_plan or {})
            if _job_looks_douyin(original_job) and retry_outputs:
                threading.Thread(
                    target=_run_resume_thread,
                    args=(
                        job_id,
                        job_resume_service,
                        run_douyin_reup_retry_job,
                        result.new_job_id,
                        job_id,
                        retry_outputs,
                        {"asr", "translation", "render"},
                        {},
                    ),
                    daemon=True,
                ).start()
            elif _job_looks_douyin(original_job):
                threading.Thread(
                    target=_run_resume_thread,
                    args=(job_id, job_resume_service, run_douyin_reup_job, result.new_job_id),
                    daemon=True,
                ).start()
            else:
                threading.Thread(
                    target=_run_resume_thread,
                    args=(job_id, job_resume_service, run_render_job, result.new_job_id),
                    daemon=True,
                ).start()
        else:
            job_resume_service.release_resume_lock(job_id)
        return result

    @app.get("/api/queue-control/jobs/{job_id}", response_model=QueueStateResponse)
    def get_queue_control_job(job_id: str) -> QueueStateResponse:
        try:
            report = queue_watchdog_service.inspect(job_id, mutate=True)
            state = report["state"]
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return QueueStateResponse(success=True, data=state, warnings=state.warnings, errors=state.errors)

    @app.post("/api/queue-control/jobs/{job_id}/pause", response_model=QueueActionResult)
    def pause_queue_job(job_id: str) -> QueueActionResult:
        try:
            return queue_control_service.request_pause(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/resume", response_model=QueueActionResult)
    def resume_queue_job(job_id: str) -> QueueActionResult:
        job_before = _get_job_or_404(job_id)
        try:
            action = queue_control_service.resume(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if job_before.get("status") in {"paused", "interrupted", "recoverable", "failed", "completed_with_errors"}:
            resume_result = _start_resume_job_for_queue(job_id, "reconcile_then_continue")
            action = action.model_copy(
                update={
                    "data": {
                        **action.data,
                        "resume_job": resume_result.model_dump(mode="json"),
                    },
                    "warnings": [*action.warnings, *resume_result.warnings],
                    "errors": [*action.errors, *resume_result.errors],
                    "success": action.success and resume_result.success,
                }
            )
        return action

    @app.post("/api/queue-control/jobs/{job_id}/cancel", response_model=QueueActionResult)
    def cancel_queue_job(job_id: str) -> QueueActionResult:
        try:
            return queue_control_service.request_cancel(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/retry-failed", response_model=QueueActionResult)
    def retry_failed_queue_items(job_id: str) -> QueueActionResult:
        try:
            action = queue_retry_service.retry_failed_items(job_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if action.affected_items:
            resume_result = _start_resume_job_for_queue(job_id, "retry_failed")
            action = action.model_copy(
                update={
                    "data": {**action.data, "resume_job": resume_result.model_dump(mode="json")},
                    "warnings": [*action.warnings, *resume_result.warnings],
                    "errors": [*action.errors, *resume_result.errors],
                    "success": action.success and resume_result.success,
                }
            )
        return action

    @app.post("/api/queue-control/jobs/{job_id}/retry-selected", response_model=QueueActionResult)
    def retry_selected_queue_items(job_id: str, request: QueueActionRequest) -> QueueActionResult:
        try:
            return queue_retry_service.retry_selected_items(job_id, request.item_ids, action=QueueControlAction.retry_selected)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/skip-selected", response_model=QueueActionResult)
    def skip_selected_queue_items(job_id: str, request: QueueActionRequest) -> QueueActionResult:
        try:
            return queue_control_service.skip_items(job_id, request.item_ids)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/prioritize-selected", response_model=QueueActionResult)
    def prioritize_selected_queue_items(job_id: str, request: QueueActionRequest) -> QueueActionResult:
        try:
            return queue_priority_service.prioritize_items(job_id, request.item_ids, QueueItemPriority.high)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/move-to-top", response_model=QueueActionResult)
    def move_queue_items_to_top(job_id: str, request: QueueActionRequest) -> QueueActionResult:
        try:
            return queue_priority_service.move_to_top(job_id, request.item_ids)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/queue-control/jobs/{job_id}/move-to-bottom", response_model=QueueActionResult)
    def move_queue_items_to_bottom(job_id: str, request: QueueActionRequest) -> QueueActionResult:
        try:
            return queue_priority_service.move_to_bottom(job_id, request.item_ids)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/queue-control/jobs/{job_id}/resource-status", response_model=ResourceStatusResponse)
    def get_queue_resource_status(job_id: str) -> ResourceStatusResponse:
        try:
            watchdog_report = queue_watchdog_service.inspect(job_id, mutate=True)
            state = watchdog_report["state"]
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        report = ResourceGuardService(state.output_dir).check_resources(state.settings or QueueSettings())
        report["watchdog"] = {
            "stale_items": watchdog_report.get("stale_items", []),
            "messages": watchdog_report.get("messages", []),
        }
        if state.concurrency_plan:
            report["concurrency_plan"] = state.concurrency_plan.model_dump(mode="json")
        return ResourceStatusResponse(success=True, data=report, warnings=list(report.get("warnings") or []), errors=[])

    @app.post("/api/source-media/scan", response_model=SourceFolderScanResult)
    def scan_source_media_folder(request: SourceFolderScanRequest) -> SourceFolderScanResult:
        try:
            return SourceMediaScanner().scan_folder(request)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể scan source media: {exc}") from exc

    @app.get("/api/source-media/folders/{folder_id}", response_model=SourceFolderScanResult)
    def get_source_media_folder(folder_id: str) -> SourceFolderScanResult:
        result = SourceMediaRepository().load_scan_result(folder_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy scan source media: {folder_id}")
        return result

    @app.post("/api/source-media/folders/{folder_id}/rescan", response_model=SourceFolderScanResult)
    def rescan_source_media_folder(folder_id: str) -> SourceFolderScanResult:
        existing = SourceMediaRepository().load_scan_result(folder_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy scan source media: {folder_id}")
        try:
            return SourceMediaScanner().scan_folder(SourceFolderScanRequest(folder_path=existing.folder_path))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể rescan source media: {exc}") from exc

    @app.post("/api/source-media/selections", response_model=SourceMediaSelectionResult)
    def create_source_media_selection(request: SourceMediaSelectionRequest) -> SourceMediaSelectionResult:
        result = SourceMediaSelectionService().create_selection(request)
        if not result.success:
            raise HTTPException(status_code=400, detail="; ".join(result.errors) or "Không thể tạo selection.")
        return result

    @app.get("/api/source-media/selections/{selection_id}", response_model=SourceMediaSelectionResult)
    def get_source_media_selection(selection_id: str) -> SourceMediaSelectionResult:
        result = SourceMediaSelectionService().get_selection(selection_id)
        if not result.success:
            raise HTTPException(status_code=404, detail="; ".join(result.errors) or "Không tìm thấy selection.")
        return result

    @app.get("/api/source-media/thumbnails/{folder_id}/{media_id}", response_class=FileResponse)
    def get_source_media_thumbnail(folder_id: str, media_id: str) -> FileResponse:
        repository = SourceMediaRepository()
        scan = repository.load_scan_result(folder_id)
        if scan is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy scan source media: {folder_id}")
        item = next((entry for entry in scan.items if entry.id == media_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy media: {media_id}")
        candidates = []
        if item.thumbnail_path:
            candidates.append(Path(item.thumbnail_path))
        candidates.append(repository.thumbnail_folder(folder_id) / f"{media_id}.jpg")
        for candidate in candidates:
            path = candidate.expanduser().resolve()
            if path.exists() and path.is_file():
                return FileResponse(path, media_type="image/jpeg", filename=path.name)
        raise HTTPException(status_code=404, detail="Chưa có thumbnail cho media này.")

    @app.get("/api/douyin-downloader/status", response_model=DouyinDownloaderStatusResponse)
    def get_douyin_downloader_status() -> DouyinDownloaderStatusResponse:
        return douyin_downloader_service.get_status()

    @app.get("/api/douyin-downloader/history", response_model=DouyinDownloaderHistoryResponse)
    def get_douyin_downloader_history() -> DouyinDownloaderHistoryResponse:
        return douyin_downloader_service.get_history()

    @app.post("/api/douyin-downloader/open-browser", response_model=DouyinDownloaderStatusResponse)
    def open_douyin_downloader_browser(request: DouyinDownloaderOpenRequest) -> DouyinDownloaderStatusResponse:
        try:
            return douyin_downloader_service.open_browser(request.start_url)
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể mở Chrome Douyin: {exc}") from exc

    @app.post("/api/douyin-downloader/check-login", response_model=DouyinDownloaderStatusResponse)
    def check_douyin_downloader_login() -> DouyinDownloaderStatusResponse:
        try:
            return douyin_downloader_service.check_login()
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể kiểm tra đăng nhập Douyin: {exc}") from exc

    @app.post("/api/douyin-downloader/close-browser", response_model=DouyinDownloaderCloseResponse)
    def close_douyin_downloader_browser() -> DouyinDownloaderCloseResponse:
        try:
            message = douyin_downloader_service.close_browser()
            return DouyinDownloaderCloseResponse(success=True, message=message)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể đóng Chrome Douyin: {exc}") from exc

    @app.post("/api/douyin-downloader/scan", response_model=DouyinDownloaderJobResponse)
    def start_douyin_downloader_scan(request: DouyinDownloaderScanRequest) -> DouyinDownloaderJobResponse:
        try:
            return douyin_downloader_service.start_scan(request.channel_url, request.max_scrolls)
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể bắt đầu quét đường dẫn Douyin: {exc}") from exc

    @app.post("/api/douyin-downloader/download", response_model=DouyinDownloaderJobResponse)
    def start_douyin_downloader_download(request: DouyinDownloaderDownloadRequest) -> DouyinDownloaderJobResponse:
        try:
            return douyin_downloader_service.start_download(
                links=request.links,
                output_folder=request.output_folder,
                skip_existing=request.skip_existing,
            )
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể bắt đầu tải video Douyin: {exc}") from exc

    @app.get("/api/douyin-downloader/jobs/{job_id}", response_model=DouyinDownloaderJobResponse)
    def get_douyin_downloader_job(job_id: str) -> DouyinDownloaderJobResponse:
        job = douyin_downloader_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ tải Douyin.")
        return job

    @app.post("/api/douyin-downloader/jobs/{job_id}/pause", response_model=DouyinDownloaderJobActionResponse)
    def pause_douyin_downloader_job(job_id: str) -> DouyinDownloaderJobActionResponse:
        try:
            return douyin_downloader_service.pause_job(job_id)
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể dừng tác vụ tải Douyin: {exc}") from exc

    @app.post("/api/douyin-downloader/jobs/{job_id}/resume", response_model=DouyinDownloaderJobActionResponse)
    def resume_douyin_downloader_job(job_id: str) -> DouyinDownloaderJobActionResponse:
        try:
            return douyin_downloader_service.resume_job(job_id)
        except DouyinDownloaderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể tiếp tục tác vụ tải Douyin: {exc}") from exc

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
                product_context=request.product_context,
            )
            config = _apply_app_settings(config)
            _require_config_ready(config, mode="douyin_reup")
            scanner = DouyinFolderScanner()
            media = scanner.scan_folder(config.source_folder)
            total_outputs = _count_douyin_selected(media, config.douyin_reup or DouyinReupSettings(enabled=True))
            if total_outputs <= 0:
                raise ValueError(f"Không tìm thấy video hợp lệ trong thư mục Douyin: {config.source_folder}")
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

    @app.post("/api/silent-reup/detect", response_model=SilentReupDetectResponse)
    def detect_silent_reup_videos(request: SilentReupDetectRequest) -> SilentReupDetectResponse:
        try:
            items = SilentReupService().detect_folder(request.source_folder)
            return SilentReupDetectResponse(success=True, items=items)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể detect video silent: {exc}") from exc

    @app.post("/api/silent-reup/plan", response_model=SilentReupPlanResponse)
    def build_silent_reup_plan(request: SilentReupPlanRequest) -> SilentReupPlanResponse:
        video_path = Path(request.video_path).expanduser().resolve()
        if not video_path.exists() or not video_path.is_file():
            raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
        try:
            settings = _silent_settings_from_payload(request.settings)
            plan_id = str(uuid.uuid4())
            output_dir = ensure_dir(video_path.parent / "_silent_reup_plans" / f"{video_path.stem}-{plan_id[:8]}")
            service = SilentReupService()
            plan = service.build_plan(
                str(video_path),
                settings=settings,
                output_dir=str(output_dir),
                product_context=request.product_context,
                gemini_api_keys=_get_app_settings().gemini_api_keys,
            )
            _SILENT_PLAN_STORE[plan_id] = {
                "plan": plan.model_dump(mode="json"),
                "settings": settings.model_dump(mode="json"),
                "output_dir": str(output_dir),
                "product_context": request.product_context,
            }
            return SilentReupPlanResponse(success=True, plan_id=plan_id, plan=plan)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể tạo silent reup plan: {exc}") from exc

    @app.get("/api/silent-caption-templates/industries", response_model=SilentCaptionIndustriesResponse)
    def get_silent_caption_industries() -> SilentCaptionIndustriesResponse:
        return SilentCaptionIndustriesResponse(items=list_silent_caption_industries())

    @app.get("/api/silent-caption-templates", response_model=SilentCaptionTemplateListResponse)
    def list_silent_caption_templates(
        industry: str | None = None,
        intent: str | None = None,
        strategy: str | None = None,
    ) -> SilentCaptionTemplateListResponse:
        items = SilentCaptionTemplateService().list_templates(
            industry=industry,
            intent=intent,
            strategy=strategy,
        )
        return SilentCaptionTemplateListResponse(items=items, total=len(items))

    @app.get(
        "/api/silent-reup/visual-tags/vocabulary",
        response_model=SilentVisualTagVocabularyResponse,
    )
    def get_silent_visual_tag_vocabulary() -> SilentVisualTagVocabularyResponse:
        return SilentVisualTagVocabularyResponse(**VISUAL_TAG_VOCABULARY)

    @app.post(
        "/api/silent-reup/plans/{plan_id}/visual-tags",
        response_model=SilentVisualTagReportResponse,
    )
    def generate_silent_visual_tags(plan_id: str) -> SilentVisualTagReportResponse:
        stored = _SILENT_PLAN_STORE.get(plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {plan_id}")
        plan = SilentReupPlan.model_validate(stored["plan"])
        service = VisualTagService()
        report = service.tag_video_segments(
            plan.video_path,
            plan.visual_segments,
            product_context=stored.get("product_context") or {},
            folder_name=Path(plan.video_path).parent.name,
            filename=Path(plan.video_path).stem,
            ocr_text_by_segment={segment.id: segment.ocr_text or "" for segment in plan.visual_segments},
        )
        segments = service.apply_report_to_segments(plan.visual_segments, report)
        plan = _plan_with_visual_tag_report(plan, segments, report)
        _save_visual_tagged_plan(plan_id, stored, plan, report)
        return SilentVisualTagReportResponse(success=True, report=report)

    @app.get(
        "/api/silent-reup/plans/{plan_id}/visual-tags",
        response_model=SilentVisualTagReportResponse,
    )
    def get_silent_visual_tags(plan_id: str) -> SilentVisualTagReportResponse:
        stored = _SILENT_PLAN_STORE.get(plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {plan_id}")
        plan = SilentReupPlan.model_validate(stored["plan"])
        report = plan.visual_tag_report
        if report is None and plan.visual_tagging.report_id:
            report = VisualTagRepository().get_report(plan.visual_tagging.report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Visual tag report not found for silent plan: {plan_id}")
        return SilentVisualTagReportResponse(success=True, report=report)

    @app.put(
        "/api/silent-reup/plans/{plan_id}/segments/{segment_id}/tags",
        response_model=SilentReupPlanResponse,
    )
    def update_silent_segment_visual_tags(
        plan_id: str,
        segment_id: str,
        request: UpdateSegmentVisualTagsRequest,
    ) -> SilentReupPlanResponse:
        stored = _SILENT_PLAN_STORE.get(plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {plan_id}")
        plan = SilentReupPlan.model_validate(stored["plan"])
        target = next((segment for segment in plan.visual_segments if segment.id == segment_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"Silent segment not found: {segment_id}")
        if request.segment_id is not None and request.segment_id != segment_id:
            raise HTTPException(status_code=400, detail="Body segment_id must match the segment_id in the URL.")
        user_tags = [
            VisualTag(
                tag=tag,
                category=TAG_CATEGORY_BY_NAME[tag],
                confidence=1.0,
                source="user",
                reason="User override",
            )
            for tag in request.tags
        ]
        primary_industry = request.primary_industry or _first_tag(user_tags, VisualTagCategory.industry)
        primary_scene = request.primary_scene or _first_tag(user_tags, VisualTagCategory.scene)
        primary_action = request.primary_action or _first_tag(user_tags, VisualTagCategory.action)
        updated_segment = target.model_copy(
            update={
                "visual_tags": user_tags,
                "primary_industry": primary_industry,
                "primary_scene": primary_scene,
                "primary_action": primary_action,
                "visual_tag_confidence": 1.0,
            }
        )
        segments = [updated_segment if segment.id == segment_id else segment for segment in plan.visual_segments]
        report = _report_from_tagged_segments(plan, segments)
        plan = _plan_with_visual_tag_report(plan, segments, report)
        VisualTagRepository().upsert_override(plan_id, segment_id, request)
        _save_visual_tagged_plan(plan_id, stored, plan, report)
        return SilentReupPlanResponse(success=True, plan_id=plan_id, plan=plan)

    @app.post(
        "/api/silent-reup/plans/{plan_id}/regenerate-captions",
        response_model=SilentReupPlanResponse,
    )
    def regenerate_silent_plan_captions(
        plan_id: str,
        request: SilentCaptionRegenerateRequest,
    ) -> SilentReupPlanResponse:
        stored = _SILENT_PLAN_STORE.get(plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {plan_id}")
        try:
            plan = SilentReupPlan.model_validate(stored["plan"])
            context = dict(stored.get("product_context") or {})
            if request.industry != "auto":
                context["industry"] = request.industry
            if not request.respect_user_tag_overrides:
                tag_service = VisualTagService()
                report = tag_service.tag_video_segments(
                    plan.video_path,
                    plan.visual_segments,
                    product_context=context,
                    folder_name=Path(plan.video_path).parent.name,
                    filename=Path(plan.video_path).stem,
                    ocr_text_by_segment={segment.id: segment.ocr_text or "" for segment in plan.visual_segments},
                )
                plan = _plan_with_visual_tag_report(
                    plan,
                    tag_service.apply_report_to_segments(plan.visual_segments, report),
                    report,
                )
            service = SilentReupService()
            regenerated = service.regenerate_captions(
                plan,
                output_dir=stored["output_dir"],
                industry=request.industry,
                tone=request.tone,
                strategy=request.strategy,
                product_context=context,
                use_visual_tags=request.use_visual_tags,
                respect_user_tag_overrides=request.respect_user_tag_overrides,
            )
            settings = DouyinReupSettings.model_validate(
                {
                    **stored["settings"],
                    "silent_caption_tone": request.tone,
                    "silent_mode_strategy": request.strategy or plan.strategy,
                }
            )
            stored.update(
                {
                    "plan": regenerated.model_dump(mode="json"),
                    "settings": settings.model_dump(mode="json"),
                    "product_context": context,
                }
            )
            return SilentReupPlanResponse(success=True, plan_id=plan_id, plan=regenerated)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/silent-reup/plans/{plan_id}/review-document",
        response_model=SilentReupReviewDocumentResponse,
    )
    def create_silent_plan_review_document(plan_id: str) -> SilentReupReviewDocumentResponse:
        stored = _SILENT_PLAN_STORE.get(plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {plan_id}")
        existing_id = stored.get("review_document_id")
        if existing_id:
            try:
                SubtitleReviewService().get_document(str(existing_id))
                return SilentReupReviewDocumentResponse(success=True, document_id=str(existing_id))
            except LookupError:
                pass
        plan = SilentReupPlan.model_validate(stored["plan"])
        settings = DouyinReupSettings.model_validate(stored["settings"])
        pipeline = SilentReupPipeline()
        caption_srt = pipeline.write_caption_srt(plan, stored["output_dir"])
        document = SubtitleReviewService().create_document_from_srt(
            video_id=f"silent_plan_{plan_id[:8]}",
            video_path=plan.video_path,
            translated_srt_path=caption_srt,
            source_srt_path=None,
            source_language=settings.source_language,
            target_language=settings.target_language,
            source_type=_silent_plan_caption_source(plan),
            context={
                "reup_mode": "silent_immersive",
                "silent_strategy": plan.strategy,
                "silent_plan_file": str(Path(stored["output_dir"]) / "silent_reup_plan.json"),
                "caption_generation": plan.caption_generation.model_dump(mode="json"),
                "visual_tagging": plan.visual_tagging.model_dump(mode="json"),
                "visual_tag_report": plan.visual_tag_report.model_dump(mode="json") if plan.visual_tag_report else None,
                "product_context": stored.get("product_context") or {},
                "settings_snapshot": settings.model_dump(mode="json"),
            },
            auto_mark_low_quality_lines=settings.auto_mark_low_quality_lines,
            enable_subtitle_rewrite_suggestions=settings.enable_subtitle_rewrite_suggestions,
            auto_generate_rewrite_for_flagged_lines=settings.auto_generate_rewrite_for_flagged_lines,
            auto_apply_safe_rewrites=settings.auto_apply_safe_rewrites,
            default_rewrite_style=settings.default_rewrite_style,
        )
        stored["review_document_id"] = document.id
        return SilentReupReviewDocumentResponse(success=True, document_id=document.id)

    @app.post("/api/silent-reup/render", response_model=SilentReupRenderResponse)
    def render_silent_reup_plan(request: SilentReupRenderRequest) -> SilentReupRenderResponse:
        stored = _SILENT_PLAN_STORE.get(request.plan_id)
        if not stored:
            raise HTTPException(status_code=404, detail=f"Silent plan not found: {request.plan_id}")
        try:
            settings = DouyinReupSettings.model_validate({**stored["settings"], **(request.settings or {})})
            plan = SilentReupPlan.model_validate(stored["plan"])
            project_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())
            config = _build_douyin_project_config_from_settings(
                project_name=f"silent-reup-{request.plan_id[:8]}",
                source_folder=str(Path(plan.video_path).parent),
                output_folder=str(Path(stored["output_dir"]).parent),
                settings=settings,
                product_context=stored.get("product_context") or {},
            )
            config = _apply_app_settings(config)
            _require_config_ready(config, mode="silent_reup")
            database.create_project(project_id, config.model_dump(mode="json"))
            database.create_job(job_id, project_id, preview_only=False, total_outputs=1)
            threading.Thread(
                target=run_silent_reup_plan_job,
                args=(
                    job_id,
                    plan.model_dump(mode="json"),
                    settings.model_dump(mode="json"),
                    stored["output_dir"],
                    config.tts.model_dump(mode="json"),
                ),
                daemon=True,
            ).start()
            return SilentReupRenderResponse(success=True, job_id=job_id)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc

    @app.post("/api/silent-reup/one-click", response_model=DouyinOneClickBatchResponse)
    def start_silent_reup_one_click(request: SilentReupOneClickRequest) -> DouyinOneClickBatchResponse:
        preset_by_strategy = {
            "chill_immersive": "silent_chill_immersive",
            "product_review_voiceover": "silent_product_voiceover",
            "sales_recut": "silent_sales_recut",
        }
        preset_id = preset_by_strategy.get(request.strategy, "silent_chill_immersive")
        try:
            preset_service = DouyinReupPresetService()
            overrides: dict[str, Any] = {
                "music_folder": request.bgm_folder,
                "visual_style_preset_id": request.visual_style_preset_id,
                "review_subtitles_before_render": request.review_before_render,
                "silent_review_before_render": request.review_before_render,
                "auto_render_after_translation": not request.review_before_render,
            }
            selected_paths = _selected_paths_from_source_selection(request.selected_video_paths, request.source_selection_id)
            process_mode = "all" if request.process_mode == "all_videos" else request.process_mode
            if selected_paths:
                process_mode = "selected"
            overrides.update(
                {
                    "process_mode": process_mode,
                    "selected_video_paths": selected_paths,
                    "source_selection_id": request.source_selection_id,
                }
            )
            if request.max_videos is not None:
                overrides["max_videos"] = request.max_videos
            overrides.update(request.advanced_overrides or {})
            settings = preset_service.apply_preset(preset_id, overrides=overrides)
            config = _build_douyin_project_config_from_settings(
                project_name=request.project_name,
                source_folder=request.source_folder,
                output_folder=request.output_folder,
                settings=settings,
                product_context=request.product_context,
            )
            config = _apply_app_settings(config)
            _require_config_ready(config, mode="silent_reup")
            scanner = DouyinFolderScanner()
            media = scanner.scan_folder(config.source_folder)
            total_outputs = _count_douyin_selected(media, config.douyin_reup or DouyinReupSettings(enabled=True))
            if total_outputs <= 0:
                raise ValueError(f"Không tìm thấy video hợp lệ trong thư mục Douyin: {config.source_folder}")
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
            preset_id=settings.preset_id or preset_id,
            preset_name=settings.preset_name or preset_id,
            total_outputs=total_outputs,
        )

    @app.post("/api/douyin-reup/process", response_model=DouyinReupProcessResponse)
    def process_douyin_reup_folder(request: DouyinReupProcessRequest) -> DouyinReupProcessResponse:
        database.init_db()
        try:
            config = _build_douyin_project_config(request)
            config = _apply_app_settings(config)
            _require_config_ready(config, mode="douyin_reup")
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

    @app.post("/api/config/requirements", response_model=ConfigRequirementCheckResponse)
    def check_config_requirements(request: ConfigRequirementCheckRequest) -> ConfigRequirementCheckResponse:
        try:
            config, has_custom_script = _config_for_requirement_check(request)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _check_config_requirements(config, mode=request.mode, has_custom_script=has_custom_script)

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
        total = database.count_projects()
        return ProjectListResponse(
            items=[
                {
                    "id": project["project_id"],
                    "project_name": project["config"].get("project_name", project["project_id"]),
                    "created_at": project["created_at"],
                }
                for project in projects
            ],
            total=total
        )

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict[str, Any]:
        database.init_db()
        project = database.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        database.delete_project(project_id)
        return {"success": True, "project_id": project_id}

    @app.post("/api/projects/{project_id}/duplicate")
    def duplicate_project(project_id: str) -> dict[str, Any]:
        database.init_db()
        project = database.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        new_project_id = str(uuid.uuid4())
        orig_name = project["config"].get("project_name", "Untitled Project")
        new_name = f"{orig_name} - Sao chép"
        new_project = database.duplicate_project(project_id, new_project_id, new_name)
        if not new_project:
            raise HTTPException(status_code=500, detail="Failed to duplicate project")
        return {"success": True, "project_id": new_project_id}


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

    @app.get("/api/projects/{project_id}/jobs")
    def list_project_jobs(project_id: str, include_preview: bool = False) -> dict[str, Any]:
        database.init_db()
        jobs = database.get_project_jobs(project_id, include_preview=include_preview)
        # Sort so latest jobs are first
        jobs = sorted(jobs, key=lambda x: x["created_at"], reverse=True)
        return {"success": True, "jobs": jobs}

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
        _require_config_ready(config, mode="product_render", has_custom_script=bool(project.get("custom_script")))
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

    @app.post("/api/tts/preview", response_model=TTSPreviewResponse)
    def preview_tts_voice(request: TTSPreviewRequest) -> TTSPreviewResponse:
        settings = _get_app_settings()
        text = request.text.strip() or settings.google_tts_preview_text
        provider = request.provider.strip().lower().replace("-", "_")
        voice = request.voice.strip()
        output_dir = ensure_dir(app_data_dir() / "previews" / "tts")
        output_path = output_dir / f"{_safe_preview_filename(provider)}_{_safe_preview_filename(voice)}.mp3"
        tts_settings = TTSSettings(
            provider=provider,
            fallback_provider="piper",
            allow_provider_fallback=False,
            allow_silent_fallback=False,
            voice=voice,
            language=request.language.strip() or "vi",
            api_key=request.api_key or settings.google_tts_api_key,
            credentials_json_path=request.credentials_json_path or settings.google_tts_credentials_json_path,
            access_token=request.access_token or settings.google_tts_access_token,
            output_format="mp3",
        )
        manager = TTSManager()
        try:
            result = manager.generate_voice(text, str(output_path), tts_settings)
        except TTSProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Không thể tạo audio nghe thử: {exc}") from exc
        return TTSPreviewResponse(
            success=True,
            path=result.output_path,
            url=f"/api/files/audio?path={quote(result.output_path)}",
            provider=result.provider,
            voice=voice,
            warnings=result.warnings,
        )

    @app.get("/api/music/library", response_model=MusicLibraryResponse)
    def get_music_library(folder_path: str | None = Query(default=None)) -> MusicLibraryResponse:
        settings = _get_app_settings()
        warnings: list[str] = []
        folder = Path(folder_path).expanduser().resolve() if folder_path else None
        tracks: list[MusicLibraryTrack] = []
        favorite_set = {_normalize_path_for_compare(path) for path in settings.favorite_music_paths}

        if folder is None:
            favorite_tracks = _music_tracks_from_paths(settings.favorite_music_paths, favorite_set=favorite_set)
            return MusicLibraryResponse(
                folder_path=None,
                tracks=favorite_tracks,
                favorite_music_paths=settings.favorite_music_paths,
                warnings=["Chưa chọn thư mục nhạc. Đang chỉ hiển thị các bài đã đánh dấu sao còn tồn tại."],
            )
        if not folder.exists() or not folder.is_dir():
            raise HTTPException(status_code=404, detail=f"Thư mục nhạc không tồn tại: {folder}")

        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_BGM_EXTENSIONS:
                continue
            track = _music_track_from_path(path, favorite_set=favorite_set, warnings=warnings)
            if track:
                tracks.append(track)
        return MusicLibraryResponse(
            folder_path=str(folder),
            tracks=tracks,
            favorite_music_paths=settings.favorite_music_paths,
            warnings=warnings,
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

    @app.get("/api/jobs")
    def list_all_jobs(limit: int = 100, offset: int = 0) -> dict[str, Any]:
        database.init_db()
        with database.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as count FROM jobs").fetchone()["count"]
            rows = conn.execute(
                """
                SELECT j.job_id, j.project_id, j.status, j.current_step, j.progress, 
                       j.total_outputs, j.completed_outputs, j.failed_outputs, 
                       j.preview_only, j.created_at, j.updated_at, p.config_json
                FROM jobs j
                LEFT JOIN projects p ON j.project_id = p.project_id
                ORDER BY j.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
        jobs = []
        for row in rows:
            job_dict = dict(row)
            project_name = None
            if job_dict.get("config_json"):
                try:
                    cfg = json.loads(job_dict["config_json"])
                    project_name = cfg.get("project_name")
                except Exception:
                    pass
            job_dict["project_name"] = project_name
            job_dict.pop("config_json", None)
            jobs.append(job_dict)
        return {"success": True, "jobs": jobs, "total": total}


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
            created_at=job.get("created_at"),
            updated_at=job.get("updated_at"),
        )

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str) -> dict[str, Any]:
        database.init_db()
        job = database.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        database.delete_job(job_id)
        return {"success": True, "job_id": job_id}


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
        all_outputs = [
            output
            for output in (original_job.get("results") or {}).get("outputs", [])
            if isinstance(output, dict) and output.get("source_video")
        ]
        if request.video_ids:
            retry_outputs = _filter_douyin_outputs_by_ids(all_outputs, request.video_ids)
        else:
            retry_outputs = [
                output
                for output in all_outputs
                if output.get("status") == "failed"
                or (isinstance(output.get("final_output_qa"), dict) and output["final_output_qa"].get("status") == "failed")
            ]
        if not retry_outputs:
            raise HTTPException(status_code=400, detail="Không tìm thấy video hợp lệ để xử lý lại bằng preset đã chọn.")

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
            failed_outputs=retry_outputs,
            retry_steps=set(request.retry_steps or ["asr", "translation", "render"]),
            settings_override=retry_settings.model_dump(mode="json"),
        )
        return DouyinRetryFailedResponse(job_id=retry_job_id, status="queued", retry_outputs=len(retry_outputs))

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

    @app.get("/api/files/audio", response_model=None)
    def get_audio_file(path: str = Query(...)) -> FileResponse:
        audio_path = Path(path).expanduser().resolve()
        if not audio_path.exists() or not audio_path.is_file():
            raise HTTPException(status_code=404, detail=f"Audio file not found: {audio_path}")
        if audio_path.suffix.lower() not in SUPPORTED_BGM_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only common audio preview files are supported.")
        try:
            audio_path.relative_to(app_data_dir().resolve())
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Audio path is not a registered Auto Tool preview asset.") from exc
        media_type = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav"
        return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)

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

    _mount_frontend(app, static_frontend_service)
    return app


def run_render_job(job_id: str) -> None:
    database.init_db()
    checkpoint_service = JobCheckpointService()
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
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
        return

    def progress_callback(payload: dict[str, Any]) -> None:
        next_status = payload.get("status") or "running"
        database.update_job(
            job_id,
            status=next_status,
            current_step=payload.get("current_step", "running"),
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )
        _checkpoint_progress(job_id, checkpoint_service, payload)

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        _ensure_job_checkpoint(checkpoint_service, job_id, "product_render", job["project_id"], project["config"], config.output_folder)
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, "starting")
        custom_script = None
        if project.get("custom_script"):
            custom_script = ProductVideoScript.model_validate(project["custom_script"])
        summary = _run_product_render_project(
            config,
            preview_only=job["preview_only"],
            custom_script=custom_script,
            project_id=job["project_id"],
            job_id=job_id,
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        _save_latest_script_from_summary(job["project_id"], summary, log_callback)
        queue_status = summary.get("queue_status")
        if queue_status in {"paused", "cancelled"}:
            status = queue_status
            current_step = queue_status
        else:
            status = "completed" if summary["failed_outputs"] == 0 else "completed_with_errors"
            current_step = "completed"
        database.update_job(
            job_id,
            status=status,
            current_step=current_step,
            progress=100 if queue_status != "paused" else int((summary["successful_outputs"] + summary["failed_outputs"]) / max(1, summary["requested_outputs"]) * 100),
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
        checkpoint_status = JobRunStatus.paused if queue_status == "paused" else JobRunStatus.cancelled if queue_status == "cancelled" else JobRunStatus.completed
        checkpoint_service.update_job_status(job_id, checkpoint_status, current_step)
        checkpoint_service.update_counts(
            job_id,
            total_items=summary["requested_outputs"],
            completed_items=summary["successful_outputs"],
            failed_items=summary["failed_outputs"],
            interrupted_items=max(0, summary["requested_outputs"] - summary["successful_outputs"] - summary["failed_outputs"]) if queue_status == "paused" else 0,
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def _run_product_render_project(
    config: ProjectConfig,
    *,
    preview_only: bool,
    custom_script: ProductVideoScript | None,
    project_id: str,
    job_id: str,
    progress_callback,
    log_callback,
) -> dict[str, Any]:
    kwargs = {
        "preview_only": preview_only,
        "custom_script": custom_script,
        "project_id": project_id,
        "progress_callback": progress_callback,
        "log_callback": log_callback,
    }
    if "job_id" in inspect.signature(render_project).parameters:
        kwargs["job_id"] = job_id
    return render_project(config, **kwargs)


def _run_resume_thread(original_job_id: str, resume_service: JobResumeService, target, *args: Any) -> None:
    try:
        target(*args)
    finally:
        resume_service.release_resume_lock(original_job_id)


def _is_douyin_resume(original_job: dict[str, Any], retry_outputs: list[dict[str, Any]]) -> bool:
    return _job_looks_douyin(original_job) and bool(retry_outputs)


def _douyin_resume_outputs(resume_plan: dict[str, Any]) -> list[dict[str, Any]]:
    selected = [str(path).strip() for path in resume_plan.get("selected_source_videos") or [] if str(path).strip()]
    items = [item for item in (resume_plan.get("retry_outputs") or []) if isinstance(item, dict)]
    items.extend(item for item in (resume_plan.get("pending_outputs") or []) if isinstance(item, dict))
    by_path: dict[str, dict[str, Any]] = {}
    for item in items:
        path = str(item.get("source_video") or "").strip()
        if not path:
            continue
        by_path[str(Path(path).expanduser().resolve()).lower()] = item
    for index, path in enumerate(selected, start=1):
        key = str(Path(path).expanduser().resolve()).lower()
        by_path.setdefault(
            key,
            {
                "index": index,
                "status": "pending",
                "source_video": path,
                "recovery_status": "pending",
            },
        )
    return sorted(by_path.values(), key=lambda item: int(item.get("index") or 0))


def _job_looks_douyin(job: dict[str, Any]) -> bool:
    outputs = (job.get("results") or {}).get("outputs") or []
    return any(isinstance(output, dict) and output.get("source_video") for output in outputs)


def _ensure_job_checkpoint(
    checkpoint_service: JobCheckpointService,
    job_id: str,
    mode: str,
    project_id: str | None,
    settings_snapshot: dict[str, Any],
    output_dir: str,
) -> None:
    if checkpoint_service.load_job_checkpoint(job_id) is not None:
        return
    checkpoint_service.create_job_checkpoint(
        job_id=job_id,
        mode=mode,
        project_id=project_id,
        settings_snapshot=settings_snapshot,
        output_dir=output_dir,
    )


def _checkpoint_progress(job_id: str, checkpoint_service: JobCheckpointService, payload: dict[str, Any]) -> None:
    checkpoint_service.update_job_status(
        job_id,
        JobRunStatus.running,
        payload.get("current_step", "running"),
    )
    total = int(payload.get("total_outputs", 0) or 0)
    completed = int(payload.get("completed_outputs", 0) or 0)
    failed = int(payload.get("failed_outputs", 0) or 0)
    checkpoint_service.update_counts(
        job_id,
        total_items=total,
        completed_items=completed,
        failed_items=failed,
        interrupted_items=max(0, total - completed - failed),
    )


def run_douyin_reup_job(job_id: str) -> None:
    database.init_db()
    checkpoint_service = JobCheckpointService()
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
        next_status = payload.get("status") or "running"
        database.update_job(
            job_id,
            status=next_status,
            current_step=payload.get("current_step", "running"),
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )
        _checkpoint_progress(job_id, checkpoint_service, payload)

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        _ensure_job_checkpoint(checkpoint_service, job_id, "douyin_reup", job["project_id"], project["config"], config.output_folder)
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, "starting")
        summary = DouyinReupService().process_folder(
            config,
            project_id=job["project_id"],
            job_id=job_id,
            progress_callback=progress_callback,
            log_callback=log_callback,
        )
        queue_status = summary.get("queue_status")
        if queue_status in {"paused", "cancelled"}:
            status = queue_status
            current_step = queue_status
        else:
            status = "completed" if summary.get("failed_outputs", 0) == 0 else "completed_with_errors"
            current_step = "completed"
        total_items = int(summary.get("processed_outputs") or job["total_outputs"])
        completed_items = int(summary.get("successful_outputs") or 0)
        failed_items = int(summary.get("failed_outputs") or 0)
        database.update_job(
            job_id,
            status=status,
            current_step=current_step,
            progress=100 if queue_status != "paused" else int((completed_items + failed_items) / max(1, job["total_outputs"]) * 100),
            total_outputs=total_items,
            completed_outputs=completed_items,
            failed_outputs=failed_items,
            output_folder=summary.get("output_folder"),
            results_json=json.dumps(
                {
                    "summary": summary,
                    "outputs": summary.get("outputs", []),
                },
                ensure_ascii=False,
            ),
        )
        checkpoint_status = JobRunStatus.paused if queue_status == "paused" else JobRunStatus.cancelled if queue_status == "cancelled" else JobRunStatus.completed
        checkpoint_service.update_job_status(job_id, checkpoint_status, current_step)
        checkpoint_service.update_counts(
            job_id,
            total_items=total_items,
            completed_items=completed_items,
            failed_items=failed_items,
            interrupted_items=max(0, job["total_outputs"] - completed_items - failed_items) if queue_status == "paused" else 0,
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=job["total_outputs"],
            error=str(exc),
        )


def run_silent_reup_plan_job(
    job_id: str,
    plan_payload: dict[str, Any],
    settings_payload: dict[str, Any],
    output_dir: str,
    tts_settings_payload: dict[str, Any] | None = None,
) -> None:
    database.init_db()
    checkpoint_service = JobCheckpointService()
    job = database.get_job(job_id)
    if not job:
        return
    last_reported_step: str | None = None

    def progress_callback(payload: dict[str, Any]) -> None:
        nonlocal last_reported_step
        step = str(payload.get("current_step") or "silent_render")
        phase_progress = max(0, min(100, int(payload.get("progress", 0))))
        database.update_job(
            job_id,
            status="running",
            current_step=f"silent_{step}",
            progress=max(10, min(95, 10 + int(phase_progress * 0.85))),
        )
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, step)
        if step != last_reported_step:
            database.add_job_log(job_id, "info", f"Silent render: {step}")
            last_reported_step = step
    try:
        database.update_job(job_id, status="running", current_step="silent_render", progress=10)
        _ensure_job_checkpoint(checkpoint_service, job_id, "silent_immersive", job.get("project_id"), {"plan": plan_payload, "settings": settings_payload}, output_dir)
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, "render")
        plan = SilentReupPlan.model_validate(plan_payload)
        settings = DouyinReupSettings.model_validate(settings_payload)
        tts_settings = TTSSettings.model_validate(tts_settings_payload or {})
        pipeline = SilentReupPipeline()
        result = pipeline.render_from_plan(
            plan,
            settings,
            output_dir,
            progress_callback=progress_callback,
            tts_settings=tts_settings,
        )
        success = result.status == "success" and bool(result.output_video_path)
        qa_summary = None
        if success and result.output_video_path:
            progress_callback({"current_step": "final_output_qa", "progress": 98})
            qa_report = FinalOutputQAService().run_qa_for_output(
                result.output_video_path,
                PlatformTarget.tiktok,
                job_id=job_id,
                project_id=job.get("project_id"),
                video_id="video_001",
                ass_path=result.caption_ass_path,
                overlay_path=result.overlay_path,
                subtitle_expected=settings.burn_subtitle,
                audio_expected=(
                    settings.keep_immersive_original_audio
                    or settings.add_bgm_for_silent_video
                    or settings.generate_voiceover_for_silent_video
                ),
                overlay_expected=settings.add_overlay,
                report_path=str(Path(output_dir) / "video_001_final_qa.json"),
            )
            qa_summary = {
                "status": qa_report.status,
                "score": qa_report.score,
                "report_path": qa_report.report_path,
                "issues": [issue.model_dump(mode="json") for issue in qa_report.issues],
            }
            if result.log_path:
                try:
                    silent_log = json.loads(Path(result.log_path).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    silent_log = result.model_dump(mode="json")
                silent_log["final_output_qa"] = qa_summary
                write_json(result.log_path, silent_log)
        output = {
            "index": 1,
            "path": result.output_video_path or "",
            "status": "success" if success else "failed",
            "source_video": result.input_video_path,
            "reup_mode": "silent_immersive",
            "silent_strategy": plan.strategy,
            "speech_score": plan.speech_score,
            "caption_source": _silent_plan_caption_source(plan),
            "translated_srt_file": result.caption_srt_path,
            "subtitle_ass_file": result.caption_ass_path,
            "overlay_file": result.overlay_path,
            "voiceover_file": result.voiceover_path,
            "voiceover_subtitle_file": result.voiceover_subtitle_path,
            "voiceover_script_file": pipeline.last_voiceover_script_path,
            "bgm_file": result.bgm_path,
            "silent_plan_file": result.plan_path,
            "log_file": result.log_path,
            "final_output_qa": qa_summary,
            "warnings": result.warnings,
            "errors": result.errors,
        }
        project = database.get_project(job.get("project_id")) if job.get("project_id") else None
        project_name = str(((project or {}).get("config") or {}).get("project_name") or f"silent-reup-{job_id[:8]}")
        summary_path = Path(output_dir) / "silent_reup_job_summary.json"
        summary = {
            "project_name": project_name,
            "output_folder": output_dir,
            "total_videos": 1,
            "processed_outputs": 1,
            "successful_outputs": 1 if success else 0,
            "failed_outputs": 0 if success else 1,
            "warnings_count": len(result.warnings),
            "subtitle_sources": {_silent_plan_caption_source(plan): 1},
            "failed_items": [] if success else [{"index": 1, "reason": "; ".join(result.errors) or "Silent render failed"}],
            "outputs": [output],
            "silent_immersive": {
                "enabled": True,
                "videos_detected_silent": 1 if not plan.has_speech else 0,
                "videos_processed_silent": 1 if success else 0,
                "strategies": {plan.strategy: 1},
                "caption_sources": {_silent_plan_caption_source(plan): 1},
            },
            "final_output_qa": _final_qa_summary_from_outputs([output]),
            "summary_file": str(summary_path),
        }
        write_json(summary_path, summary)
        database.update_job(
            job_id,
            status="completed" if success else "completed_with_errors",
            current_step="completed",
            progress=100,
            total_outputs=1,
            completed_outputs=1 if success else 0,
            failed_outputs=0 if success else 1,
            output_folder=output_dir,
            results_json=json.dumps({"summary": summary, "outputs": [output]}, ensure_ascii=False),
        )
        checkpoint_service.update_job_status(job_id, JobRunStatus.completed, "completed")
        checkpoint_service.update_counts(
            job_id,
            total_items=1,
            completed_items=1 if success else 0,
            failed_items=0 if success else 1,
            interrupted_items=0,
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
        database.update_job(
            job_id,
            status="failed",
            current_step="failed",
            progress=100,
            failed_outputs=1,
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
    checkpoint_service = JobCheckpointService()
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
        next_status = payload.get("status") or "running"
        database.update_job(
            job_id,
            status=next_status,
            current_step=f"retry_{payload.get('current_step', 'running')}",
            progress=int(payload.get("progress", 0)),
            total_outputs=int(payload.get("total_outputs", job["total_outputs"])),
            completed_outputs=int(payload.get("completed_outputs", 0)),
            failed_outputs=int(payload.get("failed_outputs", 0)),
        )
        _checkpoint_progress(job_id, checkpoint_service, payload)

    def log_callback(level: str, message: str) -> None:
        database.add_job_log(job_id, level, message)

    try:
        database.update_job(job_id, status="running", current_step="retry_starting", progress=1)
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        _ensure_job_checkpoint(checkpoint_service, job_id, "douyin_reup", job["project_id"], {"retry_of_job_id": original_job_id, "config": project["config"]}, config.output_folder)
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, "starting")
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
        queue_status = summary.get("queue_status")
        if queue_status in {"paused", "cancelled"}:
            status = queue_status
            current_step = queue_status
        else:
            status = "completed" if summary.get("failed_outputs", 0) == 0 else "completed_with_errors"
            current_step = "completed"
        total_items = int(summary.get("processed_outputs") or job["total_outputs"])
        completed_items = int(summary.get("successful_outputs") or 0)
        failed_items = int(summary.get("failed_outputs") or 0)
        database.update_job(
            job_id,
            status=status,
            current_step=current_step,
            progress=100 if queue_status != "paused" else int((completed_items + failed_items) / max(1, job["total_outputs"]) * 100),
            total_outputs=total_items,
            completed_outputs=completed_items,
            failed_outputs=failed_items,
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
        checkpoint_status = JobRunStatus.paused if queue_status == "paused" else JobRunStatus.cancelled if queue_status == "cancelled" else JobRunStatus.completed
        checkpoint_service.update_job_status(job_id, checkpoint_status, current_step)
        checkpoint_service.update_counts(
            job_id,
            total_items=total_items,
            completed_items=completed_items,
            failed_items=failed_items,
            interrupted_items=max(0, job["total_outputs"] - completed_items - failed_items) if queue_status == "paused" else 0,
        )
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
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
    checkpoint_service = JobCheckpointService()
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
    silent_pipeline = SilentReupPipeline(render_pipeline=pipeline)
    review_service = SubtitleReviewService()
    tts_settings = _tts_settings_from_app_settings()

    try:
        database.update_job(job_id, status="running", current_step="render_approved_subtitles", progress=1)
        _ensure_job_checkpoint(
            checkpoint_service,
            job_id,
            "subtitle_render",
            job.get("project_id"),
            {"document_ids": document_ids, "settings": settings_payload},
            str(output_root),
        )
        checkpoint_service.update_job_status(job_id, JobRunStatus.running, "render")
        for index, document_id in enumerate(document_ids, start=1):
            checkpoint_service.mark_step_started(
                job_id,
                f"video_{index:03d}",
                document_id,
                RecoverableStep.render,
                {"subtitle_review_document_id": document_id},
            )
            try:
                document_dir = ensure_dir(output_root / f"video_{index:03d}")
                log_path = document_dir / f"video_{index:03d}_log.json"
                document = review_service.get_document(document_id)
                is_silent = (document.context or {}).get("reup_mode") == "silent_immersive"
                document_settings = settings
                if is_silent and isinstance((document.context or {}).get("settings_snapshot"), dict):
                    document_settings = DouyinReupSettings.model_validate(
                        {
                            **document.context["settings_snapshot"],
                            "review_subtitles_before_render": False,
                            "silent_review_before_render": False,
                            "auto_render_after_translation": True,
                        }
                    )
                result = (
                    silent_pipeline.render_review_document(
                        document,
                        document_settings,
                        str(document_dir),
                        tts_settings=tts_settings,
                    )
                    if is_silent
                    else pipeline.render_from_review_document(
                        document_id,
                        document_settings,
                        str(document_dir),
                        tts_settings=tts_settings,
                    )
                )
                qa_report = FinalOutputQAService().run_qa_for_output(
                    str(result["path"]),
                    PlatformTarget.tiktok,
                    job_id=job_id,
                    project_id=job.get("project_id"),
                    video_id=f"video_{index:03d}",
                    ass_path=result.get("corrected_ass_file") or result.get("subtitle_ass_file"),
                    overlay_path=result.get("overlay_file"),
                    subtitle_expected=document_settings.burn_subtitle,
                    audio_expected=(
                        document_settings.keep_immersive_original_audio
                        or document_settings.add_bgm_for_silent_video
                        or document_settings.generate_voiceover_for_silent_video
                    ) if is_silent else (
                        document_settings.keep_original_audio
                        or document_settings.add_bgm
                        or document_settings.generate_voiceover_for_silent_video
                    ),
                    overlay_expected=document_settings.add_overlay,
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
                        "reup_mode": result.get("reup_mode"),
                        "silent_strategy": result.get("silent_strategy"),
                        "voiceover_file": result.get("voiceover_file"),
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
                        "subtitle_source": result.get("caption_source") if is_silent else document.source_type,
                        "source_srt_file": result.get("source_srt_file"),
                        "translated_srt_file": result.get("translated_srt_file"),
                        "corrected_srt_file": result.get("corrected_srt_file"),
                        "subtitle_ass_file": result.get("subtitle_ass_file"),
                        "corrected_ass_file": result.get("corrected_ass_file"),
                        "overlay_file": result.get("overlay_file"),
                        "bgm_file": result.get("bgm_file"),
                        "voiceover_file": result.get("voiceover_file"),
                        "voiceover_script_file": result.get("voiceover_script_file"),
                        "voiceover_subtitle_file": result.get("voiceover_subtitle_file"),
                        "reup_mode": result.get("reup_mode"),
                        "silent_strategy": result.get("silent_strategy"),
                        "speech_score": result.get("speech_score"),
                        "caption_source": result.get("caption_source"),
                        "silent_plan_file": result.get("silent_plan_file"),
                        "log_file": str(log_path),
                        "duration": result.get("duration"),
                        "warnings": result.get("warnings") or [],
                        "errors": result.get("errors") or [],
                        "subtitle_review_document_id": document_id,
                        "final_output_qa": qa_summary,
                    }
                )
                completed += 1
                checkpoint_service.mark_step_completed(
                    job_id,
                    f"video_{index:03d}",
                    RecoverableStep.render,
                    {"video": str(result.get("path") or "")},
                )
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
                checkpoint_service.mark_step_failed(job_id, f"video_{index:03d}", RecoverableStep.render, str(exc))

            database.update_job(
                job_id,
                status="running",
                current_step=f"subtitle_review_render_{index}",
                progress=max(1, min(99, int(index / max(total, 1) * 95))),
                total_outputs=total,
                completed_outputs=completed,
                failed_outputs=failed,
            )
            checkpoint_service.update_counts(
                job_id,
                total_items=total,
                completed_items=completed,
                failed_items=failed,
                interrupted_items=max(0, total - completed - failed),
            )

        status = "completed" if failed == 0 else "completed_with_errors"
        project = database.get_project(job.get("project_id")) if job.get("project_id") else None
        project_name = str(((project or {}).get("config") or {}).get("project_name") or f"subtitle-review-{job_id[:8]}")
        summary_path = output_root / "subtitle_review_render_summary.json"
        summary = {
            "project_name": project_name,
            "output_folder": str(output_root),
            "total_videos": total,
            "processed_outputs": len(outputs),
            "successful_outputs": completed,
            "failed_outputs": failed,
            "warnings_count": sum(len(output.get("warnings") or []) for output in outputs),
            "subtitle_sources": dict(
                Counter(str(output.get("subtitle_source") or "reviewed") for output in outputs)
            ),
            "failed_items": [
                {"index": output.get("index") or 0, "reason": output.get("error_message") or "Render failed"}
                for output in outputs
                if output.get("status") == "failed"
            ],
            "outputs": outputs,
            "silent_immersive": {
                "enabled": any(output.get("reup_mode") == "silent_immersive" for output in outputs),
                "videos_detected_silent": sum(1 for output in outputs if output.get("reup_mode") == "silent_immersive"),
                "videos_processed_silent": sum(
                    1 for output in outputs if output.get("reup_mode") == "silent_immersive" and output.get("status") == "success"
                ),
                "strategies": dict(
                    Counter(
                        str(output.get("silent_strategy") or "unknown")
                        for output in outputs
                        if output.get("reup_mode") == "silent_immersive"
                    )
                ),
            },
            "final_output_qa": _final_qa_summary_from_outputs(outputs),
            "summary_file": str(summary_path),
        }
        write_json(summary_path, summary)
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
        checkpoint_service.update_job_status(job_id, JobRunStatus.completed, "completed")
        checkpoint_service.update_counts(job_id, total_items=total, completed_items=completed, failed_items=failed, interrupted_items=0)
    except Exception as exc:
        database.add_job_log(job_id, "error", str(exc))
        checkpoint_service.update_job_status(job_id, JobRunStatus.failed, "failed")
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


def _config_for_requirement_check(request: ConfigRequirementCheckRequest) -> tuple[ProjectConfig | None, bool]:
    if request.project_config is not None:
        return _apply_app_settings(request.project_config), False
    if request.project_id:
        database.init_db()
        project = database.get_project(request.project_id)
        if not project:
            raise LookupError(f"Project not found: {request.project_id}")
        config = _apply_app_settings(ProjectConfig.model_validate(project["config"]))
        return config, bool(project.get("custom_script"))
    return None, False


def _require_config_ready(
    config: ProjectConfig,
    *,
    mode: str,
    has_custom_script: bool = False,
) -> None:
    result = _check_config_requirements(config, mode=mode, has_custom_script=has_custom_script)
    if result.errors_count:
        raise HTTPException(status_code=400, detail=_config_requirements_error_detail(result))


def _check_config_requirements(
    config: ProjectConfig | None,
    *,
    mode: str,
    has_custom_script: bool = False,
) -> ConfigRequirementCheckResponse:
    load_local_env()
    issues: list[ConfigRequirementIssue] = []

    if _gemini_required_for_mode(config, mode, has_custom_script=has_custom_script):
        if not _has_gemini_key(config):
            if _script_fallback_enabled():
                issues.append(
                    ConfigRequirementIssue(
                        severity="warning",
                        code="gemini_missing_using_fallback",
                        field="settings.gemini_api_keys",
                        message=(
                            "Chưa có Gemini API key. Tool sẽ dùng kịch bản dự phòng vì "
                            "AUTO_TOOL_ALLOW_SCRIPT_FALLBACK đang bật."
                        ),
                        action="Nhập Gemini API key trong trang Cài đặt để tạo script/dịch subtitle bằng AI.",
                    )
                )
            else:
                issues.append(
                    ConfigRequirementIssue(
                        severity="error",
                        code="missing_gemini_api_key",
                        field="settings.gemini_api_keys",
                        message=(
                            "Chưa cấu hình Gemini API key. Tác vụ này cần Gemini để tạo hoặc dịch nội dung video."
                        ),
                        action="Vào Cài đặt > API key, nhập ít nhất một Gemini API key rồi lưu lại.",
                    )
                )

    if _google_tts_required_for_mode(config, mode):
        auth = _google_tts_auth_values(config)
        if not any(auth.values()):
            issues.append(
                ConfigRequirementIssue(
                    severity="error",
                    code="missing_google_tts_credentials",
                    field="settings.google_tts_credentials_json_path",
                    message="Bạn đang chọn Google Cloud TTS nhưng chưa cung cấp API key, access token hoặc file service account JSON.",
                    action="Vào Cài đặt > API key, nhập Google TTS API key hoặc chọn file service account JSON.",
                )
            )
        credential_path = auth.get("credentials_json_path")
        if credential_path and not Path(credential_path).expanduser().exists():
            issues.append(
                ConfigRequirementIssue(
                    severity="error",
                    code="google_tts_credentials_file_missing",
                    field="settings.google_tts_credentials_json_path",
                    message=f"File service account Google TTS không tồn tại: {credential_path}",
                    action="Chọn lại đúng file JSON trong trang Cài đặt hoặc bỏ trống nếu dùng API key/access token.",
                )
            )

    settings = config.douyin_reup if config else None
    if settings and _bgm_required_for_settings(settings, mode):
        has_favorite_bgm = _has_valid_favorite_bgm_file(settings.favorite_music_paths)
        if not settings.music_folder and not has_favorite_bgm:
            issues.append(
                ConfigRequirementIssue(
                    severity="error",
                    code="missing_bgm_folder",
                    field="settings.music_folder",
                    message="Bạn đã bật nhạc nền nhưng chưa chọn thư mục nhạc.",
                    action="Chọn thư mục có file .mp3/.wav/.m4a hoặc tắt mục Thêm nhạc nền.",
                )
            )
        elif settings.music_folder:
            music_folder = Path(settings.music_folder).expanduser()
            if (not music_folder.exists() or not music_folder.is_dir()) and not has_favorite_bgm:
                issues.append(
                    ConfigRequirementIssue(
                        severity="error",
                        code="bgm_folder_not_found",
                        field="settings.music_folder",
                        message=f"Thư mục nhạc nền không tồn tại: {settings.music_folder}",
                        action="Chọn lại đúng thư mục nhạc nền hoặc tắt mục Thêm nhạc nền.",
                    )
                )
            elif not _has_supported_bgm_file(music_folder) and not has_favorite_bgm:
                issues.append(
                    ConfigRequirementIssue(
                        severity="error",
                        code="bgm_folder_empty",
                        field="settings.music_folder",
                        message=f"Thư mục nhạc nền không có file audio hợp lệ: {settings.music_folder}",
                        action="Thêm file .mp3/.wav/.m4a/.aac/.flac/.ogg/.opus hoặc tắt mục Thêm nhạc nền.",
                )
            )

    issues.extend(_overlay_requirement_issues(config, mode))
    issues.extend(_product_music_requirement_issues(config, mode))

    errors_count = sum(1 for issue in issues if issue.severity == "error")
    warnings_count = sum(1 for issue in issues if issue.severity == "warning")
    return ConfigRequirementCheckResponse(
        ready=errors_count == 0,
        errors_count=errors_count,
        warnings_count=warnings_count,
        issues=issues,
    )


def _config_requirements_error_detail(result: ConfigRequirementCheckResponse) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Thiếu cấu hình bắt buộc trước khi render.",
        "issues": [issue.model_dump(mode="json") for issue in result.issues],
    }


def _gemini_required_for_mode(
    config: ProjectConfig | None,
    mode: str,
    *,
    has_custom_script: bool = False,
) -> bool:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "product_render":
        return not has_custom_script
    settings = config.douyin_reup if config else None
    if normalized_mode == "douyin_reup":
        return settings is None or _normalized_provider(settings.translation_provider) == "gemini"
    if normalized_mode == "silent_reup":
        if settings is None:
            return True
        return bool(settings.generate_visual_captions) or _normalized_provider(settings.translation_provider) == "gemini"
    return False


def _google_tts_required_for_mode(config: ProjectConfig | None, mode: str) -> bool:
    if config is None:
        return False
    providers = {_normalized_provider(config.tts.provider)}
    settings = config.douyin_reup
    if settings and settings.generate_voiceover_for_silent_video:
        providers.add(_normalized_provider(settings.silent_voiceover_provider))
    return "google_cloud_tts" in providers


def _bgm_required_for_settings(settings: DouyinReupSettings, mode: str) -> bool:
    normalized_mode = mode.strip().lower()
    if normalized_mode == "silent_reup":
        return bool(settings.add_bgm_for_silent_video)
    if normalized_mode == "douyin_reup":
        if settings.enable_silent_immersive_mode and settings.preset_id and settings.preset_id.startswith("silent_"):
            return bool(settings.add_bgm_for_silent_video)
        return bool(settings.add_bgm)
    return False


def _has_valid_favorite_bgm_file(paths: list[str]) -> bool:
    for item in paths:
        try:
            path = Path(item).expanduser()
            if path.is_file() and path.suffix.lower() in SUPPORTED_BGM_EXTENSIONS and path.stat().st_size > 0:
                return True
        except OSError:
            continue
    return False


def _overlay_requirement_issues(config: ProjectConfig | None, mode: str) -> list[ConfigRequirementIssue]:
    if config is None:
        return []

    normalized_mode = mode.strip().lower()
    overlay_path: str | None = None
    custom_overlay_required = False
    field = "visual_style.custom_overlay_path"
    if normalized_mode == "product_render" and config.visual_style.overlay_mode == "custom":
        overlay_path = config.visual_style.custom_overlay_path
        custom_overlay_required = True
    elif normalized_mode in {"douyin_reup", "silent_reup"} and config.douyin_reup:
        settings = config.douyin_reup
        if settings.add_overlay and settings.overlay_mode == "custom":
            overlay_path = settings.custom_overlay_path
            custom_overlay_required = True
            field = "douyin_reup.custom_overlay_path"

    if not custom_overlay_required:
        return []

    try:
        select_custom_overlay_asset(overlay_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return [
            ConfigRequirementIssue(
                severity="error",
                code="custom_overlay_missing_or_invalid",
                field=field,
                message=f"Overlay custom không hợp lệ: {exc}",
                action="Chọn file .png/.jpg/.jpeg/.webp hoặc thư mục có ảnh overlay nền trong suốt trước khi render.",
            )
        ]
    return []


def _product_music_requirement_issues(config: ProjectConfig | None, mode: str) -> list[ConfigRequirementIssue]:
    if config is None or mode.strip().lower() != "product_render" or not config.music.enabled:
        return []
    selector = MusicSelector()
    selected = selector.select_music(config, output_index=1)
    if selected:
        return []
    message = "; ".join(selector.warnings) or "Đã bật nhạc nền nhưng chưa chọn được file nhạc hợp lệ."
    return [
        ConfigRequirementIssue(
            severity="error",
            code="product_music_missing_or_invalid",
            field="music.source_folder",
            message=f"Đã bật nhạc nền nhưng không có file nhạc hợp lệ để render: {message}",
            action="Chọn lại thư mục/file nhạc hợp lệ hoặc tắt mục Thêm nhạc nền trước khi render.",
        )
    ]


def _has_supported_bgm_file(folder: Path) -> bool:
    return any(
        path.is_file() and path.suffix.lower() in SUPPORTED_BGM_EXTENSIONS and path.stat().st_size > 0
        for path in folder.iterdir()
    )


def _has_gemini_key(config: ProjectConfig | None) -> bool:
    settings = _get_app_settings()
    candidates: list[str] = []
    if config is not None:
        candidates.extend(config.ai.gemini_api_keys)
    candidates.extend(settings.gemini_api_keys)
    candidates.extend(_split_env_keys(os.getenv("GEMINI_API_KEYS", "")))
    candidates.append(os.getenv("GEMINI_API_KEY", ""))
    return any(candidate.strip() for candidate in candidates)


def _google_tts_auth_values(config: ProjectConfig | None) -> dict[str, str]:
    settings = _get_app_settings()
    return {
        "api_key": (
            (config.tts.api_key if config else None)
            or settings.google_tts_api_key
            or os.getenv("GOOGLE_TTS_API_KEY")
            or os.getenv("GOOGLE_CLOUD_TTS_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip(),
        "credentials_json_path": (
            (config.tts.credentials_json_path if config else None)
            or settings.google_tts_credentials_json_path
            or os.getenv("GOOGLE_TTS_CREDENTIALS_JSON_PATH")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            or ""
        ).strip(),
        "access_token": (
            (config.tts.access_token if config else None)
            or settings.google_tts_access_token
            or os.getenv("GOOGLE_TTS_ACCESS_TOKEN")
            or ""
        ).strip(),
    }


def _has_google_tts_auth() -> bool:
    return any(_google_tts_auth_values(None).values())


def _script_fallback_enabled() -> bool:
    return os.getenv("AUTO_TOOL_ALLOW_SCRIPT_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}


def _normalized_provider(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def _split_env_keys(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", "\n").replace(",", "\n").splitlines() if part.strip()]


def _silent_settings_from_payload(payload: dict[str, Any] | None = None) -> DouyinReupSettings:
    base = DouyinReupSettings(enabled=True).model_dump(mode="json")
    updates = dict(payload or {})
    updates.setdefault("enabled", True)
    updates.setdefault("preset_id", "silent_chill_immersive")
    updates.setdefault("preset_name", "Không thoại - Chill immersive")
    updates.setdefault("enable_silent_immersive_mode", True)
    updates.setdefault("silent_mode_strategy", "chill_immersive")
    return DouyinReupSettings.model_validate({**base, **updates})


def _silent_plan_caption_source(plan: SilentReupPlan) -> str:
    sources = [caption.source for caption in plan.captions]
    if "ocr_translation" in sources:
        return "ocr_translation"
    if "visual_generated" in sources:
        return "visual_generated"
    return sources[0] if sources else "template"


def _first_tag(tags: list[VisualTag], category: VisualTagCategory) -> str | None:
    return next((tag.tag for tag in tags if tag.category == category), None)


def _report_from_tagged_segments(
    plan: SilentReupPlan,
    segments: list,
) -> VideoVisualTagReport:
    segment_results = [
        SegmentVisualTagResult(
            segment_id=segment.id,
            video_path=segment.video_path,
            start=segment.start,
            end=segment.end,
            tags=segment.visual_tags,
            primary_industry=segment.primary_industry,
            primary_scene=segment.primary_scene,
            primary_action=segment.primary_action,
            confidence=segment.visual_tag_confidence,
            warnings=[],
        )
        for segment in segments
    ]
    strongest: dict[str, VisualTag] = {}
    for result in segment_results:
        for tag in result.tags:
            current = strongest.get(tag.tag)
            if current is None or tag.confidence > current.confidence or tag.source == "user":
                strongest[tag.tag] = tag
    industry_scores: Counter[str] = Counter()
    for result in segment_results:
        if result.primary_industry:
            industry_scores[result.primary_industry] += result.confidence or 0.1
    recommended_industry = (
        industry_scores.most_common(1)[0][0]
        if industry_scores
        else plan.visual_tagging.recommended_industry
    )
    action_counts = Counter(result.primary_action for result in segment_results if result.primary_action)
    if action_counts["comparison"] or action_counts["before_after"] or action_counts["result_showcase"] >= 2:
        recommended_strategy = "sales_recut"
    elif action_counts["testing"] or action_counts["usage_demo"] >= 3:
        recommended_strategy = "product_review_voiceover"
    else:
        recommended_strategy = "chill_immersive"
    average_confidence = (
        sum(result.confidence for result in segment_results) / len(segment_results)
        if segment_results
        else 0.0
    )
    return VideoVisualTagReport(
        video_path=plan.video_path,
        project_id=plan.visual_tag_report.project_id if plan.visual_tag_report else None,
        job_id=plan.visual_tag_report.job_id if plan.visual_tag_report else None,
        segment_results=segment_results,
        video_level_tags=sorted(strongest.values(), key=lambda item: (-item.confidence, item.tag)),
        recommended_industry=recommended_industry or "general_product",
        recommended_strategy=recommended_strategy,
        average_confidence=round(average_confidence, 4),
        warnings=[],
        created_at=(
            plan.visual_tag_report.created_at
            if plan.visual_tag_report
            else datetime.now().replace(microsecond=0).isoformat()
        ),
    )


def _plan_with_visual_tag_report(
    plan: SilentReupPlan,
    segments: list,
    report: VideoVisualTagReport,
) -> SilentReupPlan:
    metadata = plan.visual_tagging.model_copy(
        update={
            "enabled": True,
            "recommended_industry": report.recommended_industry or "general_product",
            "recommended_strategy": report.recommended_strategy or "chill_immersive",
            "average_confidence": report.average_confidence,
            "tag_sources": dict(Counter(tag.source for result in report.segment_results for tag in result.tags)),
            "warnings": report.warnings,
        }
    )
    return plan.model_copy(
        update={
            "visual_segments": segments,
            "visual_tagging": metadata,
            "visual_tag_report": report,
        }
    )


def _save_visual_tagged_plan(
    plan_id: str,
    stored: dict[str, Any],
    plan: SilentReupPlan,
    report: VideoVisualTagReport,
) -> None:
    try:
        report_id = VisualTagRepository().save_report(report)
        plan.visual_tagging = plan.visual_tagging.model_copy(update={"report_id": report_id})
    except Exception as exc:
        plan.visual_tagging = plan.visual_tagging.model_copy(
            update={"warnings": [*plan.visual_tagging.warnings, f"Could not persist visual tag report: {exc}"]}
        )
    stored["plan"] = plan.model_dump(mode="json")
    write_json(Path(stored["output_dir"]) / "silent_reup_plan.json", stored["plan"])
    _SILENT_PLAN_STORE[plan_id] = stored


def _build_douyin_project_config(request: DouyinReupProcessRequest) -> ProjectConfig:
    selected_paths = _selected_paths_from_source_selection(
        request.selected_video_paths or request.settings.selected_video_paths,
        request.source_selection_id or request.settings.source_selection_id,
    )
    settings = request.settings
    updates: dict[str, Any] = {}
    if selected_paths:
        updates["process_mode"] = "selected"
        updates["selected_video_paths"] = selected_paths
    if request.source_selection_id or request.settings.source_selection_id:
        updates["source_selection_id"] = request.source_selection_id or request.settings.source_selection_id
    if updates:
        settings = settings.model_copy(update=updates)
    return _build_douyin_project_config_from_settings(
        project_name=request.project_name,
        source_folder=request.source_folder,
        output_folder=request.output_folder,
        settings=settings,
    )


def _build_douyin_project_config_from_settings(
    *,
    project_name: str,
    source_folder: str,
    output_folder: str,
    settings: DouyinReupSettings,
    product_context: dict[str, Any] | None = None,
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
            "product": _douyin_product_payload(product_context),
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
            "industry": {
                "preset_id": str(
                    (product_context or {}).get("industry")
                    or (product_context or {}).get("category")
                    or "general_product"
                )
            },
            "douyin_reup": settings.model_dump(mode="json"),
        }
    )


def _douyin_product_payload(product_context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = product_context or {}
    features = context.get("features") or ["Dịch subtitle", "Thêm overlay", "Trộn nhạc nền"]
    if isinstance(features, str):
        features = [line.strip() for line in features.splitlines() if line.strip()]
    if not isinstance(features, list) or not features:
        features = ["Dịch subtitle", "Thêm overlay", "Trộn nhạc nền"]
    return {
        "name": str(context.get("product_name") or context.get("name") or "Douyin Reup").strip() or "Douyin Reup",
        "brand": str(context.get("brand") or "").strip(),
        "description": str(
            context.get("description") or "Xử lý video Douyin local với subtitle/caption tiếng Việt."
        ).strip(),
        "features": [str(item).strip() for item in features if str(item).strip()],
        "cta": str(context.get("cta") or "Xem video").strip() or "Xem video",
    }


def _one_click_overrides(request: DouyinOneClickBatchRequest) -> dict[str, Any]:
    process_mode = "all" if request.process_mode == "all_videos" else request.process_mode
    selected_paths = _selected_paths_from_source_selection(request.selected_video_paths, request.source_selection_id)
    if selected_paths:
        process_mode = "selected"
    overrides: dict[str, Any] = {
        "process_mode": process_mode,
        "selected_video_paths": selected_paths,
        "source_selection_id": request.source_selection_id,
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


def _selected_paths_from_source_selection(explicit_paths: list[str] | None, source_selection_id: str | None) -> list[str]:
    selected_paths = [str(path).strip() for path in (explicit_paths or []) if str(path).strip()]
    if selected_paths:
        return selected_paths
    selection_id = (source_selection_id or "").strip()
    if not selection_id:
        return []
    result = SourceMediaSelectionService().get_selection(selection_id)
    if not result.success:
        raise ValueError("; ".join(result.errors) or f"Không tìm thấy source selection: {selection_id}")
    if not result.selected_paths:
        raise ValueError(f"Source selection không có video hợp lệ: {selection_id}")
    return result.selected_paths


def _normalize_douyin_settings(settings: DouyinReupSettings, base_dir: Path) -> DouyinReupSettings:
    updates: dict[str, Any] = {}
    if settings.music_folder:
        updates["music_folder"] = str(resolve_path(settings.music_folder, base_dir, must_exist=True))
    if settings.overlay_mode == "custom" and settings.custom_overlay_path:
        updates["custom_overlay_path"] = str(
            resolve_path(settings.custom_overlay_path, base_dir, must_exist=True)
        )
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
            "preset_id": "silent_chill_immersive",
            "reason": "Many videos have no audio, so Silent Immersive can generate Vietnamese visual captions without ASR.",
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
    preferred_google_voice = _pick_favorite_google_voice(settings)
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
    if preferred_google_voice:
        tts_updates["provider"] = "google_cloud_tts"
        tts_updates["voice"] = preferred_google_voice

    music_updates: dict[str, Any] = {}
    if settings.favorite_music_paths:
        music_updates["favorite_music_paths"] = settings.favorite_music_paths

    douyin_updates: dict[str, Any] = {}
    if settings.favorite_music_paths:
        douyin_updates["favorite_music_paths"] = settings.favorite_music_paths
    if preferred_google_voice:
        douyin_updates["silent_voiceover_provider"] = "google_cloud_tts"
        douyin_updates["silent_voiceover_voice"] = preferred_google_voice

    updates: dict[str, Any] = {}
    if ai_updates:
        updates["ai"] = config.ai.model_copy(update=ai_updates)
    if tts_updates:
        updates["tts"] = config.tts.model_copy(update=tts_updates)
    if music_updates:
        updates["music"] = config.music.model_copy(update=music_updates)
    if douyin_updates and config.douyin_reup:
        updates["douyin_reup"] = config.douyin_reup.model_copy(update=douyin_updates)
    return config.model_copy(update=updates) if updates else config


def _tts_settings_from_app_settings() -> TTSSettings:
    settings = _get_app_settings()
    preferred_google_voice = _pick_favorite_google_voice(settings)
    updates: dict[str, Any] = {}
    if settings.google_tts_api_key:
        updates["api_key"] = settings.google_tts_api_key
    if settings.google_tts_credentials_json_path:
        updates["credentials_json_path"] = settings.google_tts_credentials_json_path
    if settings.google_tts_access_token:
        updates["access_token"] = settings.google_tts_access_token
    if preferred_google_voice:
        updates["provider"] = "google_cloud_tts"
        updates["voice"] = preferred_google_voice
    return TTSSettings().model_copy(update=updates) if updates else TTSSettings()


def _pick_favorite_google_voice(settings: AppSettings) -> str | None:
    voices = [voice.strip() for voice in settings.google_tts_favorite_voices if voice.strip()]
    if not voices:
        return None
    return random.choice(voices)


def _safe_preview_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return cleaned.strip("_")[:80] or "preview"


def _normalize_path_for_compare(path: str) -> str:
    try:
        return str(Path(path).expanduser().resolve()).casefold()
    except OSError:
        return path.strip().casefold()


def _music_tracks_from_paths(paths: list[str], *, favorite_set: set[str]) -> list[MusicLibraryTrack]:
    tracks: list[MusicLibraryTrack] = []
    warnings: list[str] = []
    for item in paths:
        path = Path(item).expanduser()
        track = _music_track_from_path(path, favorite_set=favorite_set, warnings=warnings)
        if track:
            tracks.append(track)
    return tracks


def _music_track_from_path(
    path: Path,
    *,
    favorite_set: set[str],
    warnings: list[str],
) -> MusicLibraryTrack | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError as exc:
        warnings.append(f"Bỏ qua file nhạc không đọc được {path}: {exc}")
        return None
    if not resolved.exists() or not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_BGM_EXTENSIONS:
        return None
    size_bytes = resolved.stat().st_size
    if size_bytes <= 0:
        warnings.append(f"Bỏ qua file nhạc rỗng: {resolved}")
        return None
    duration: float | None = None
    try:
        duration = round(float(probe_media_duration(str(resolved))), 3)
    except Exception as exc:
        warnings.append(f"Không đọc được duration của {resolved.name}: {exc}")
    return MusicLibraryTrack(
        path=str(resolved),
        filename=resolved.name,
        size_bytes=size_bytes,
        duration=duration,
        favorite=_normalize_path_for_compare(str(resolved)) in favorite_set,
    )


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


def _mount_frontend(app: FastAPI, service: StaticFrontendService | None = None) -> None:
    frontend_service = service or StaticFrontendService()
    status = frontend_service.get_status()
    if not status["enabled"]:
        return

    dist_dir = frontend_service.get_frontend_dist_path()
    index_file = dist_dir / "index.html"
    assets_dir = frontend_service.get_static_assets_path()
    if not index_file.exists():
        return

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def serve_frontend(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        requested = (dist_dir / full_path).resolve()
        try:
            requested.relative_to(dist_dir)
        except ValueError:
            requested = index_file

        if requested.is_file() and requested != index_file:
            return FileResponse(requested)
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
