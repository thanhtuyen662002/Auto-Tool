from __future__ import annotations

import json
import uuid

from app import database
from app.modules.subtitle_quality.subtitle_quality_schema import SubtitleDocumentQualityReport


class SubtitleQualityRepository:
    def upsert(self, report: SubtitleDocumentQualityReport) -> SubtitleDocumentQualityReport:
        database.init_db()
        now = report.created_at
        report_id = self._existing_id(report.document_id) or str(uuid.uuid4())
        payload = report.model_dump(mode="json")
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO subtitle_quality_reports (
                    id, document_id, project_id, video_id,
                    average_score, total_lines, needs_review_count,
                    critical_count, warning_count, report_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    video_id = excluded.video_id,
                    average_score = excluded.average_score,
                    total_lines = excluded.total_lines,
                    needs_review_count = excluded.needs_review_count,
                    critical_count = excluded.critical_count,
                    warning_count = excluded.warning_count,
                    report_json = excluded.report_json,
                    updated_at = excluded.updated_at
                """,
                (
                    report_id,
                    report.document_id,
                    report.project_id,
                    report.video_id,
                    report.average_score,
                    report.total_lines,
                    report.needs_review_count,
                    report.critical_count,
                    report.warning_count,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        saved = self.get(report.document_id)
        assert saved is not None
        return saved

    def get(self, document_id: str) -> SubtitleDocumentQualityReport | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT report_json FROM subtitle_quality_reports WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if not row:
            return None
        return SubtitleDocumentQualityReport.model_validate(json.loads(row["report_json"]))

    def list_by_document_ids(self, document_ids: list[str]) -> list[SubtitleDocumentQualityReport]:
        if not document_ids:
            return []
        database.init_db()
        placeholders = ",".join("?" for _ in document_ids)
        with database.get_connection() as conn:
            rows = conn.execute(
                f"SELECT report_json FROM subtitle_quality_reports WHERE document_id IN ({placeholders})",
                document_ids,
            ).fetchall()
        return [SubtitleDocumentQualityReport.model_validate(json.loads(row["report_json"])) for row in rows]

    def _existing_id(self, document_id: str) -> str | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM subtitle_quality_reports WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return str(row["id"]) if row else None
