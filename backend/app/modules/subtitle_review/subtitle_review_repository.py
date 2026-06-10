from __future__ import annotations

import json
from typing import Any

from app import database
from app.modules.subtitle_review.subtitle_review_schema import (
    SubtitleLine,
    SubtitleReviewDocument,
    SubtitleReviewStatus,
)
from app.modules.subtitle_quality.subtitle_quality_repository import SubtitleQualityRepository


class SubtitleReviewRepository:
    def create(self, document: SubtitleReviewDocument) -> SubtitleReviewDocument:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO subtitle_review_documents (
                    id, project_id, job_id, video_id, video_path,
                    source_language, target_language, source_type,
                    source_srt_path, translated_srt_path, corrected_srt_path, corrected_ass_path,
                    status, line_count, reviewed_count, edited_count, warning_count,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _document_values(document),
            )
            self._replace_lines(conn, document.id, document.lines, document.created_at, document.updated_at)
        saved = self.get(document.id)
        assert saved is not None
        return saved

    def list(
        self,
        *,
        project_id: str | None = None,
        job_id: str | None = None,
        status: str | None = None,
    ) -> list[SubtitleReviewDocument]:
        database.init_db()
        where, values = _filter_clause(project_id=project_id, job_id=job_id, status=status)
        with database.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM subtitle_review_documents
                {where}
                ORDER BY created_at DESC, updated_at DESC
                """,
                values,
            ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def get(self, document_id: str) -> SubtitleReviewDocument | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM subtitle_review_documents WHERE id = ?", (document_id,)).fetchone()
        return self._row_to_document(row) if row else None

    def update_document(self, document: SubtitleReviewDocument) -> SubtitleReviewDocument:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                UPDATE subtitle_review_documents
                SET project_id = ?, job_id = ?, video_id = ?, video_path = ?,
                    source_language = ?, target_language = ?, source_type = ?,
                    source_srt_path = ?, translated_srt_path = ?, corrected_srt_path = ?, corrected_ass_path = ?,
                    status = ?, line_count = ?, reviewed_count = ?, edited_count = ?, warning_count = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    document.project_id,
                    document.job_id,
                    document.video_id,
                    document.video_path,
                    document.source_language,
                    document.target_language,
                    document.source_type,
                    document.source_srt_path,
                    document.translated_srt_path,
                    document.corrected_srt_path,
                    document.corrected_ass_path,
                    document.status.value,
                    document.line_count,
                    document.reviewed_count,
                    document.edited_count,
                    document.warning_count,
                    document.updated_at,
                    document.id,
                ),
            )
            self._replace_lines(conn, document.id, document.lines, document.created_at, document.updated_at)
        saved = self.get(document.id)
        assert saved is not None
        return saved

    def update_line(self, document_id: str, line: SubtitleLine, updated_at: str) -> SubtitleLine | None:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                UPDATE subtitle_review_lines
                SET start_ms = ?, end_ms = ?, source_text = ?, translated_text = ?,
                    edited_text = ?, status = ?, warnings_json = ?, user_note = ?,
                    rewrite_history_json = ?, updated_at = ?
                WHERE document_id = ? AND line_index = ?
                """,
                (
                    line.start_ms,
                    line.end_ms,
                    line.source_text,
                    line.translated_text,
                    line.edited_text,
                    line.status.value,
                    json.dumps(line.warnings, ensure_ascii=False),
                    line.user_note,
                    json.dumps(line.rewrite_history, ensure_ascii=False),
                    updated_at,
                    document_id,
                    line.index,
                ),
            )
        document = self.get(document_id)
        if not document:
            return None
        return next((item for item in document.lines if item.index == line.index), None)

    def is_known_video_path(self, path: str) -> bool:
        target = path
        database.init_db()
        with database.get_connection() as conn:
            rows = conn.execute("SELECT video_path FROM subtitle_review_documents").fetchall()
        from pathlib import Path

        try:
            resolved = Path(target).expanduser().resolve()
        except OSError:
            return False
        for row in rows:
            try:
                if Path(row["video_path"]).expanduser().resolve() == resolved:
                    return True
            except OSError:
                continue
        return False

    def _replace_lines(self, conn: Any, document_id: str, lines: list[SubtitleLine], created_at: str, updated_at: str) -> None:
        conn.execute("DELETE FROM subtitle_review_lines WHERE document_id = ?", (document_id,))
        for line in lines:
            conn.execute(
                """
                INSERT INTO subtitle_review_lines (
                    id, document_id, line_index, start_ms, end_ms,
                    source_text, translated_text, edited_text,
                    status, warnings_json, user_note, rewrite_history_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{document_id}:{line.index}",
                    document_id,
                    line.index,
                    line.start_ms,
                    line.end_ms,
                    line.source_text,
                    line.translated_text,
                    line.edited_text,
                    line.status.value,
                    json.dumps(line.warnings, ensure_ascii=False),
                    line.user_note,
                    json.dumps(line.rewrite_history, ensure_ascii=False),
                    created_at,
                    updated_at,
                ),
            )

    def _row_to_document(self, row: Any) -> SubtitleReviewDocument:
        with database.get_connection() as conn:
            line_rows = conn.execute(
                """
                SELECT *
                FROM subtitle_review_lines
                WHERE document_id = ?
                ORDER BY line_index ASC
                """,
                (row["id"],),
            ).fetchall()
        lines = [_row_to_line(line_row) for line_row in line_rows]
        document = SubtitleReviewDocument(
            id=row["id"],
            project_id=row["project_id"],
            job_id=row["job_id"],
            video_id=row["video_id"],
            video_path=row["video_path"],
            source_language=row["source_language"],
            target_language=row["target_language"],
            source_type=row["source_type"] if "source_type" in row.keys() else None,
            source_srt_path=row["source_srt_path"],
            translated_srt_path=row["translated_srt_path"],
            corrected_srt_path=row["corrected_srt_path"],
            corrected_ass_path=row["corrected_ass_path"],
            status=SubtitleReviewStatus(row["status"]),
            lines=lines,
            line_count=int(row["line_count"]),
            reviewed_count=int(row["reviewed_count"]),
            edited_count=int(row["edited_count"]),
            warning_count=int(row["warning_count"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        return _hydrate_quality(document)


def _document_values(document: SubtitleReviewDocument) -> tuple[Any, ...]:
    return (
        document.id,
        document.project_id,
        document.job_id,
        document.video_id,
        document.video_path,
        document.source_language,
        document.target_language,
        document.source_type,
        document.source_srt_path,
        document.translated_srt_path,
        document.corrected_srt_path,
        document.corrected_ass_path,
        document.status.value,
        document.line_count,
        document.reviewed_count,
        document.edited_count,
        document.warning_count,
        document.created_at,
        document.updated_at,
    )


def _filter_clause(*, project_id: str | None, job_id: str | None, status: str | None) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        values.append(project_id)
    if job_id:
        clauses.append("job_id = ?")
        values.append(job_id)
    if status:
        clauses.append("status = ?")
        values.append(status)
    if not clauses:
        return "", values
    return f"WHERE {' AND '.join(clauses)}", values


def _row_to_line(row: Any) -> SubtitleLine:
    warnings = json.loads(row["warnings_json"] or "[]")
    return SubtitleLine(
        index=int(row["line_index"]),
        start_ms=int(row["start_ms"]),
        end_ms=int(row["end_ms"]),
        source_text=row["source_text"],
        translated_text=row["translated_text"],
        edited_text=row["edited_text"],
        status=SubtitleReviewStatus(row["status"]),
        warnings=warnings,
        user_note=row["user_note"],
        rewrite_history=json.loads(row["rewrite_history_json"] or "[]") if "rewrite_history_json" in row.keys() else [],
    )


def _hydrate_quality(document: SubtitleReviewDocument) -> SubtitleReviewDocument:
    report = SubtitleQualityRepository().get(document.id)
    if report is None:
        return document
    quality_by_index = {line.line_index: line for line in report.lines}
    lines: list[SubtitleLine] = []
    for line in document.lines:
        quality = quality_by_index.get(line.index)
        if quality is None:
            lines.append(line)
            continue
        lines.append(
            line.model_copy(
                update={
                    "quality_score": quality.score,
                    "quality_needs_review": quality.needs_review,
                    "quality_severity": quality.severity.value,
                    "quality_issues": quality.issues,
                }
            )
        )
    return document.model_copy(
        update={
            "lines": lines,
            "quality_average_score": report.average_score,
            "quality_needs_review_count": report.needs_review_count,
            "quality_critical_count": report.critical_count,
            "quality_warning_count": report.warning_count,
        }
    )
