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
from app.modules.industry_presets.industry_registry import get_industry_preset
from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.modules.industry_presets.industry_schema import IndustryPreset, IndustrySettings
from app.modules.output_review.review_service import OutputQualityReviewService, build_review_rows
from app.modules.product_drafts import CreateProductDraftRequest, ProductDraftService
from app.modules.product_import import ProductImportService, suggest_industry_preset, to_project_product_info
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
    BulkSegmentReviewRequest,
    BulkSegmentReviewResponse,
    ContentExportFile,
    ContentExportResponse,
    ContentItemsResponse,
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
)
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json
from app.utils.app_paths import app_data_dir, frontend_dist_dir
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

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=_APP_VERSION)

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

    return config.model_copy(
        update={
            "source_folder": str(resolve_path(config.source_folder, base_dir, must_exist=True)),
            "output_folder": str(resolve_path(config.output_folder, base_dir)),
            "music": music,
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
