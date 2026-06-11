from __future__ import annotations

import json
import uuid
from datetime import datetime

from app import database
from app.modules.silent_visual_tagging.visual_tag_schema import (
    UpdateSegmentVisualTagsRequest,
    VideoVisualTagReport,
)


class VisualTagRepository:
    def save_report(self, report: VideoVisualTagReport) -> str:
        database.init_db()
        now = _now()
        report_id = str(uuid.uuid4())
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO silent_visual_tag_reports (
                    id, job_id, project_id, video_path, report_json,
                    recommended_industry, recommended_strategy, average_confidence,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    report.job_id,
                    report.project_id,
                    report.video_path,
                    json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
                    report.recommended_industry,
                    report.recommended_strategy,
                    report.average_confidence,
                    now,
                    now,
                ),
            )
        return report_id

    def get_report(self, report_id: str) -> VideoVisualTagReport | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT report_json FROM silent_visual_tag_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
        return VideoVisualTagReport.model_validate_json(row["report_json"]) if row else None

    def get_latest_for_video(self, video_path: str) -> tuple[str, VideoVisualTagReport] | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, report_json
                FROM silent_visual_tag_reports
                WHERE video_path = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (video_path,),
            ).fetchone()
        if not row:
            return None
        return str(row["id"]), VideoVisualTagReport.model_validate_json(row["report_json"])

    def upsert_override(
        self,
        plan_id: str,
        segment_id: str,
        request: UpdateSegmentVisualTagsRequest,
    ) -> dict:
        database.init_db()
        now = _now()
        override_id = f"{plan_id}:{segment_id}"
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO silent_segment_tag_overrides (
                    id, plan_id, segment_id, tags_json,
                    primary_industry, primary_scene, primary_action,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(plan_id, segment_id) DO UPDATE SET
                    tags_json = excluded.tags_json,
                    primary_industry = excluded.primary_industry,
                    primary_scene = excluded.primary_scene,
                    primary_action = excluded.primary_action,
                    updated_at = excluded.updated_at
                """,
                (
                    override_id,
                    plan_id,
                    segment_id,
                    json.dumps(request.tags, ensure_ascii=False),
                    request.primary_industry,
                    request.primary_scene,
                    request.primary_action,
                    now,
                    now,
                ),
            )
        return self.get_override(plan_id, segment_id) or {}

    def get_override(self, plan_id: str, segment_id: str) -> dict | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM silent_segment_tag_overrides
                WHERE plan_id = ? AND segment_id = ?
                """,
                (plan_id, segment_id),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["tags"] = json.loads(payload.pop("tags_json") or "[]")
        return payload

    def list_overrides(self, plan_id: str) -> list[dict]:
        database.init_db()
        with database.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM silent_segment_tag_overrides WHERE plan_id = ? ORDER BY segment_id",
                (plan_id,),
            ).fetchall()
        result = []
        for row in rows:
            payload = dict(row)
            payload["tags"] = json.loads(payload.pop("tags_json") or "[]")
            result.append(payload)
        return result


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
