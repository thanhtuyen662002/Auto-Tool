from __future__ import annotations

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

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
from app.modules.output_review.review_service import OutputQualityReviewService, build_review_rows
from app.modules.output_review.rerender_service import RerenderService
from app.modules.render_worker.render_worker import render_project
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.segmenter.segmenter import Segmenter
from app.modules.script_variants.script_variant_generator import ScriptVariantGenerator
from app.modules.script_variants.variant_registry import list_variant_styles
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.timeline_templates.template_registry import list_timeline_templates
from app.modules.tts.tts_manager import list_tts_providers
from app.modules.tts.providers.google_cloud_tts_provider import list_google_cloud_voices
from app.modules.tts.providers.base import TTSProviderError
from app.presets import get_default_presets
from app.schemas.api_schema import (
    AppSettings,
    ContentExportFile,
    ContentExportResponse,
    ContentItemsResponse,
    ExportContentRequest,
    HealthResponse,
    GenerateScriptVariantsRequest,
    GenerateScriptVariantsResponse,
    JobResultsResponse,
    JobStatusResponse,
    LatestScriptResponse,
    OutputReviewResponse,
    PresetItem,
    ProjectCreateResponse,
    ProjectDetailResponse,
    RenderRequest,
    RenderResponse,
    RerenderRequest,
    RerenderResponse,
    ScanResponse,
    SegmentScoringResponse,
    ScriptVariantStyleItem,
    ScriptVariantStylesResponse,
    ScriptVariantSummaryItem,
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
)
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json
from app.utils.app_paths import frontend_dist_dir
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


def create_app() -> FastAPI:
    app = FastAPI(title="Auto Tool API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
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

    @app.post("/api/projects", response_model=ProjectCreateResponse)
    def create_project(config: ProjectConfig) -> ProjectCreateResponse:
        database.init_db()
        normalized_config = _normalize_config(config)
        project_id = str(uuid.uuid4())
        database.create_project(project_id, normalized_config.model_dump(mode="json"))
        return ProjectCreateResponse(project_id=project_id, status="created")

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

    @app.post("/api/projects/{project_id}/render", response_model=RenderResponse)
    def render_project_endpoint(project_id: str, request: RenderRequest) -> RenderResponse:
        project = _get_project_or_404(project_id)
        config = ProjectConfig.model_validate(project["config"])
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
            results_json=json.dumps({"outputs": summary["outputs"]}, ensure_ascii=False),
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
            results_json=json.dumps({"outputs": summary["outputs"]}, ensure_ascii=False),
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
