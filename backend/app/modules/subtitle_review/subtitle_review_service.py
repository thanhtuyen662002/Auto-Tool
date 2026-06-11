from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from app.modules.subtitle_review.subtitle_export_service import SubtitleExportService
from app.modules.subtitle_review.subtitle_parser import parse_srt_to_lines
from app.modules.subtitle_review.subtitle_review_repository import SubtitleReviewRepository
from app.modules.subtitle_review.subtitle_review_schema import (
    ApproveSubtitleDocumentRequest,
    SaveSubtitleReviewRequest,
    SubtitleLine,
    SubtitleReviewDocument,
    SubtitleReviewStatus,
    UpdateSubtitleLineRequest,
)
from app.modules.subtitle_review.subtitle_validation_service import SubtitleValidationService
from app.modules.subtitle_quality.subtitle_quality_service import SubtitleQualityService
from app.utils.file_utils import write_json


class SubtitleReviewService:
    def __init__(
        self,
        repository: SubtitleReviewRepository | None = None,
        validator: SubtitleValidationService | None = None,
        exporter: SubtitleExportService | None = None,
        quality_service: SubtitleQualityService | None = None,
    ) -> None:
        self.repository = repository or SubtitleReviewRepository()
        self.validator = validator or SubtitleValidationService()
        self.exporter = exporter or SubtitleExportService()
        self.quality_service = quality_service or SubtitleQualityService(review_repository=self.repository)

    def create_document_from_srt(
        self,
        video_id: str,
        video_path: str,
        translated_srt_path: str,
        source_srt_path: str | None = None,
        project_id: str | None = None,
        job_id: str | None = None,
        source_language: str = "zh",
        target_language: str = "vi",
        source_type: str | None = None,
        context: dict | None = None,
        auto_mark_low_quality_lines: bool = True,
        enable_subtitle_rewrite_suggestions: bool = True,
        auto_generate_rewrite_for_flagged_lines: bool = False,
        auto_apply_safe_rewrites: bool = False,
        default_rewrite_style: str = "short_natural",
    ) -> SubtitleReviewDocument:
        now = _now()
        lines = parse_srt_to_lines(translated_srt_path, source_srt_path=source_srt_path)
        document = SubtitleReviewDocument(
            id=str(uuid.uuid4()),
            project_id=project_id,
            job_id=job_id,
            video_id=video_id,
            video_path=video_path,
            source_language=source_language,
            target_language=target_language,
            source_type=source_type,
            context=dict(context or {}),
            source_srt_path=source_srt_path,
            translated_srt_path=translated_srt_path,
            status=SubtitleReviewStatus.pending,
            lines=lines,
            line_count=len(lines),
            reviewed_count=0,
            edited_count=0,
            warning_count=sum(len(line.warnings) for line in lines),
            created_at=now,
            updated_at=now,
        )
        document = self.validator.validate_document(document, video_duration_ms=_duration_ms(video_path))
        saved = self.repository.create(document)
        self.quality_service.create_quality_report_for_document(
            saved.id,
            auto_mark_low_quality_lines=auto_mark_low_quality_lines,
        )
        if enable_subtitle_rewrite_suggestions and auto_generate_rewrite_for_flagged_lines:
            from app.modules.subtitle_rewrite.subtitle_rewrite_schema import (
                BulkRewriteFlaggedLinesRequest,
                SubtitleRewriteStyle,
            )
            from app.modules.subtitle_rewrite.subtitle_rewrite_service import SubtitleRewriteService

            SubtitleRewriteService(review_repository=self.repository).generate_suggestions_for_flagged_lines(
                saved.id,
                BulkRewriteFlaggedLinesRequest(
                    style=SubtitleRewriteStyle(default_rewrite_style),
                    auto_apply_safe_suggestions=auto_apply_safe_rewrites,
                ),
            )
        saved = self.get_document(saved.id)
        _write_review_log(saved)
        return saved

    def list_documents(
        self,
        project_id: str | None = None,
        job_id: str | None = None,
        status: str | None = None,
    ) -> list[SubtitleReviewDocument]:
        if status:
            SubtitleReviewStatus(status)
        return self.repository.list(project_id=project_id, job_id=job_id, status=status)

    def get_document(self, document_id: str) -> SubtitleReviewDocument:
        document = self.repository.get(document_id)
        if document is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        return document

    def update_line(
        self,
        document_id: str,
        line_index: int,
        request: UpdateSubtitleLineRequest,
    ) -> SubtitleLine:
        document = self.get_document(document_id)
        target = next((line for line in document.lines if line.index == line_index), None)
        if target is None:
            raise LookupError(f"Subtitle line not found: {line_index}")
        updated = target.model_copy(
            update={
                key: value
                for key, value in {
                    "edited_text": request.edited_text,
                    "status": request.status,
                    "user_note": request.user_note,
                }.items()
                if value is not None
            }
        )
        if request.edited_text is not None and request.status is None:
            updated = updated.model_copy(update={"status": SubtitleReviewStatus.reviewed})
        updated = self.validator.validate_line(updated, video_duration_ms=_duration_ms(document.video_path))
        saved_line = self.repository.update_line(document_id, updated, _now())
        if saved_line is None:
            raise LookupError(f"Subtitle review document not found: {document_id}")
        self._refresh_document_counts(document_id)
        self.quality_service.refresh_quality_report(document_id)
        refreshed = self.get_document(document_id)
        return next(item for item in refreshed.lines if item.index == line_index)

    def save_document(
        self,
        document_id: str,
        request: SaveSubtitleReviewRequest,
    ) -> SubtitleReviewDocument:
        document = self.get_document(document_id)
        status = SubtitleReviewStatus.reviewed if request.mark_as_reviewed else document.status
        lines = [
            line.model_copy(update={"status": SubtitleReviewStatus.reviewed})
            if request.mark_as_reviewed and line.status == SubtitleReviewStatus.pending
            else line
            for line in request.lines
        ]
        updated = document.model_copy(update={"lines": lines, "status": status, "updated_at": _now()})
        updated = self.validator.validate_document(updated, video_duration_ms=_duration_ms(document.video_path))
        saved = self.repository.update_document(updated)
        self.quality_service.refresh_quality_report(document_id)
        return self.get_document(saved.id)

    def approve_document(
        self,
        document_id: str,
        request: ApproveSubtitleDocumentRequest,
    ) -> SubtitleReviewDocument:
        document = self.get_document(document_id)
        document = self.validator.validate_document(document, video_duration_ms=_duration_ms(document.video_path))
        quality_report = self.quality_service.refresh_quality_report(document_id)
        document = self.get_document(document_id)
        corrected_srt_path = self.exporter.export_corrected_srt(document)
        corrected_ass_path = None
        if request.generate_ass:
            corrected_ass_path = self.exporter.export_corrected_ass(
                document,
                visual_style_preset_id=request.visual_style_preset_id,
            )
        updated_lines = [
            line.model_copy(update={"status": SubtitleReviewStatus.approved})
            if line.status != SubtitleReviewStatus.needs_fix
            else line
            for line in document.lines
        ]
        updated = document.model_copy(
            update={
                "corrected_srt_path": corrected_srt_path,
                "corrected_ass_path": corrected_ass_path,
                "status": SubtitleReviewStatus.approved,
                "lines": updated_lines,
                "updated_at": _now(),
            }
        )
        updated = self.validator.validate_document(updated, video_duration_ms=_duration_ms(document.video_path))
        if updated.status != SubtitleReviewStatus.approved:
            updated = updated.model_copy(update={"status": SubtitleReviewStatus.approved})
        saved = self.repository.update_document(updated)
        approval_warning = _approval_quality_warning(quality_report)
        if approval_warning:
            saved = saved.model_copy(
                update={
                    "approval_quality_warning": approval_warning,
                    "approval_quality_guard": {
                        "average_score": quality_report.average_score,
                        "needs_review_count": quality_report.needs_review_count,
                        "critical_count": quality_report.critical_count,
                        "warning_count": quality_report.warning_count,
                    },
                }
            )
        _write_approve_log(saved)
        return saved

    def export_current_srt(self, document_id: str) -> SubtitleReviewDocument:
        document = self.get_document(document_id)
        corrected_srt_path = self.exporter.export_corrected_srt(document)
        updated = document.model_copy(update={"corrected_srt_path": corrected_srt_path, "updated_at": _now()})
        return self.repository.update_document(updated)

    def _refresh_document_counts(self, document_id: str) -> SubtitleReviewDocument:
        document = self.get_document(document_id)
        updated = self.validator.validate_document(document, video_duration_ms=_duration_ms(document.video_path))
        return self.repository.update_document(updated.model_copy(update={"updated_at": _now()}))


def _duration_ms(video_path: str) -> int | None:
    try:
        from app.adapters.ffmpeg_adapter import probe_video

        media = probe_video(video_path)
        return int(media.duration * 1000)
    except Exception:
        return None


def _write_review_log(document: SubtitleReviewDocument) -> None:
    log_path = Path(document.translated_srt_path).parent / "subtitle_review_log.json"
    write_json(
        log_path,
        {
            "document_id": document.id,
            "video_id": document.video_id,
            "source_srt_path": document.source_srt_path,
            "source_type": document.source_type,
            "context": document.context,
            "translated_srt_path": document.translated_srt_path,
            "line_count": document.line_count,
            "warning_count": document.warning_count,
            "status": document.status.value,
        },
    )


def _write_approve_log(document: SubtitleReviewDocument) -> None:
    log_path = Path(document.translated_srt_path).parent / "subtitle_review_approve_log.json"
    write_json(
        log_path,
        {
            "document_id": document.id,
            "status": document.status.value,
            "edited_count": document.edited_count,
            "corrected_srt_path": document.corrected_srt_path,
            "corrected_ass_path": document.corrected_ass_path,
            "approval_quality_warning": document.approval_quality_warning,
            "approval_quality_guard": document.approval_quality_guard,
        },
    )


def _approval_quality_warning(report) -> str | None:
    if report.critical_count > 0:
        return (
            f"Còn {report.critical_count} dòng phụ đề lỗi nghiêm trọng. "
            "Nên review critical lines trước khi render."
        )
    if report.needs_review_count > 0:
        return f"Còn {report.needs_review_count} dòng cần kiểm tra."
    return None


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
