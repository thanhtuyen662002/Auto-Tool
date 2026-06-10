from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils.app_paths import app_data_dir, backend_dir
from app.utils.env_loader import load_local_env


def _default_db_path() -> Path:
    if getattr(sys, "frozen", False):
        return app_data_dir() / "data" / "autotool.db"
    return backend_dir() / "data" / "autotool.db"


load_local_env()
DB_PATH = Path(os.getenv("AUTO_TOOL_DB_PATH", _default_db_path()))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                config_json TEXT NOT NULL,
                latest_script_json TEXT,
                custom_script_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                total_outputs INTEGER NOT NULL DEFAULT 0,
                completed_outputs INTEGER NOT NULL DEFAULT 0,
                failed_outputs INTEGER NOT NULL DEFAULT 0,
                preview_only INTEGER NOT NULL DEFAULT 0,
                output_folder TEXT,
                results_json TEXT NOT NULL DEFAULT '{"outputs": []}',
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            CREATE TABLE IF NOT EXISTS output_reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                output_index INTEGER NOT NULL,
                review_status TEXT NOT NULL,
                user_note TEXT,
                quality_score_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, output_index),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS output_content_items (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                output_index INTEGER NOT NULL,
                video_path TEXT NOT NULL,
                hook TEXT,
                caption TEXT NOT NULL,
                hashtags_json TEXT NOT NULL,
                cta TEXT,
                variant_style_id TEXT,
                timeline_template_id TEXT,
                publish_status TEXT NOT NULL,
                platform TEXT,
                user_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, output_index),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS source_media_reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                media_path TEXT NOT NULL,
                review_status TEXT NOT NULL,
                user_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, media_path),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS segment_reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                segment_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                start REAL NOT NULL,
                end REAL NOT NULL,
                review_status TEXT NOT NULL,
                user_note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, segment_id),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );

            CREATE TABLE IF NOT EXISTS product_drafts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,

                source_name TEXT,
                source_url TEXT,
                imported_by TEXT,
                imported_at TEXT,

                raw_input_json TEXT,
                raw_text TEXT,
                structured_data_json TEXT,
                extractor_debug_json TEXT,

                normalized_product_json TEXT,
                validation_issues_json TEXT,

                industry_preset_id TEXT,
                confidence_score REAL,

                user_note TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_product_drafts_status
            ON product_drafts(status);

            CREATE INDEX IF NOT EXISTS idx_product_drafts_created_at
            ON product_drafts(created_at);

            CREATE TABLE IF NOT EXISTS product_assets (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                draft_id TEXT,

                source_name TEXT,
                source_url TEXT,
                original_url TEXT,

                asset_type TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,

                filename TEXT,
                local_path TEXT,

                width INTEGER,
                height INTEGER,
                file_size INTEGER,
                mime_type TEXT,

                quality_score REAL,
                is_selected INTEGER NOT NULL DEFAULT 0,
                user_note TEXT,

                warnings_json TEXT,
                errors_json TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_product_assets_project_id
            ON product_assets(project_id);

            CREATE INDEX IF NOT EXISTS idx_product_assets_draft_id
            ON product_assets(draft_id);

            CREATE TABLE IF NOT EXISTS subtitle_review_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                job_id TEXT,
                video_id TEXT NOT NULL,
                video_path TEXT NOT NULL,

                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                source_type TEXT,

                source_srt_path TEXT,
                translated_srt_path TEXT NOT NULL,
                corrected_srt_path TEXT,
                corrected_ass_path TEXT,

                status TEXT NOT NULL,

                line_count INTEGER NOT NULL,
                reviewed_count INTEGER NOT NULL DEFAULT 0,
                edited_count INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subtitle_review_lines (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,

                line_index INTEGER NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,

                source_text TEXT,
                translated_text TEXT NOT NULL,
                edited_text TEXT,

                status TEXT NOT NULL,
                warnings_json TEXT,
                user_note TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                UNIQUE(document_id, line_index)
            );

            CREATE INDEX IF NOT EXISTS idx_subtitle_review_documents_job_id
            ON subtitle_review_documents(job_id);

            CREATE INDEX IF NOT EXISTS idx_subtitle_review_documents_project_id
            ON subtitle_review_documents(project_id);

            CREATE INDEX IF NOT EXISTS idx_subtitle_review_lines_document_id
            ON subtitle_review_lines(document_id);

            CREATE TABLE IF NOT EXISTS subtitle_quality_reports (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL UNIQUE,
                project_id TEXT,
                video_id TEXT,

                average_score REAL NOT NULL,
                total_lines INTEGER NOT NULL,
                needs_review_count INTEGER NOT NULL,
                critical_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,

                report_json TEXT NOT NULL,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_subtitle_quality_document_id
            ON subtitle_quality_reports(document_id);

            CREATE TABLE IF NOT EXISTS subtitle_rewrite_suggestions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                line_index INTEGER NOT NULL,
                source_text TEXT,
                original_translation TEXT NOT NULL,
                suggested_text TEXT NOT NULL,
                style TEXT NOT NULL,
                reason TEXT,
                char_count_before INTEGER NOT NULL,
                char_count_after INTEGER NOT NULL,
                estimated_cps_before REAL,
                estimated_cps_after REAL,
                safety_warnings_json TEXT,
                quality_score_before REAL,
                quality_score_after REAL,
                created_at TEXT NOT NULL,
                applied_at TEXT,
                auto_applied INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_subtitle_rewrite_document_line
            ON subtitle_rewrite_suggestions(document_id, line_index);
            """
        )
        _ensure_column(conn, "projects", "latest_script_json", "TEXT")
        _ensure_column(conn, "projects", "custom_script_json", "TEXT")
        _ensure_column(conn, "product_drafts", "extractor_debug_json", "TEXT")
        _ensure_column(conn, "subtitle_review_documents", "source_type", "TEXT")
        _ensure_column(conn, "subtitle_review_lines", "rewrite_history_json", "TEXT")
        _ensure_column(conn, "subtitle_rewrite_suggestions", "applied_at", "TEXT")
        _ensure_column(conn, "subtitle_rewrite_suggestions", "auto_applied", "INTEGER NOT NULL DEFAULT 0")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_project(project_id: str, config: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (project_id, status, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, "created", json.dumps(config, ensure_ascii=False), now, now),
        )
    project = get_project(project_id)
    assert project is not None
    return project


def get_project(project_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def list_projects(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM projects
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, min(limit, 500)), max(0, offset)),
        ).fetchall()
    return [_row_to_project(row) for row in rows]


def update_project_config(project_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE projects
            SET config_json = ?, updated_at = ?
            WHERE project_id = ?
            """,
            (json.dumps(config, ensure_ascii=False), _now(), project_id),
        )
    return get_project(project_id)


def update_project_latest_script(project_id: str, script: dict[str, Any]) -> None:
    _update_project_script(project_id, "latest_script_json", script)


def update_project_custom_script(project_id: str, script: dict[str, Any]) -> None:
    _update_project_script(project_id, "custom_script_json", script)


def create_job(job_id: str, project_id: str, preview_only: bool, total_outputs: int) -> dict[str, Any]:
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                job_id, project_id, status, current_step, progress, total_outputs,
                completed_outputs, failed_outputs, preview_only, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, project_id, "queued", "queued", 0, total_outputs, 0, 0, int(preview_only), now, now),
        )
    job = get_job(job_id)
    assert job is not None
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def get_project_jobs(project_id: str, include_preview: bool = False) -> list[dict[str, Any]]:
    query = "SELECT * FROM jobs WHERE project_id = ?"
    values: list[Any] = [project_id]
    if not include_preview:
        query += " AND preview_only = 0"
    query += " ORDER BY created_at ASC, updated_at ASC"

    with get_connection() as conn:
        rows = conn.execute(query, values).fetchall()
    return [_row_to_job(row) for row in rows]


def update_job(job_id: str, **updates: Any) -> None:
    if not updates:
        return

    allowed = {
        "status",
        "current_step",
        "progress",
        "total_outputs",
        "completed_outputs",
        "failed_outputs",
        "output_folder",
        "results_json",
        "error",
    }
    fields = {key: value for key, value in updates.items() if key in allowed}
    if not fields:
        return

    fields["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(job_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)


def add_job_log(job_id: str, level: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO job_logs (job_id, created_at, level, message)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, _now(), level, message),
        )


def get_job_logs(job_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT created_at, level, message
            FROM job_logs
            WHERE job_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (job_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_output_review(
    project_id: str,
    output_index: int,
    review_status: str,
    user_note: str | None = None,
    quality_score: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    review_id = _output_review_id(project_id, output_index)
    quality_score_json = json.dumps(quality_score, ensure_ascii=False) if quality_score is not None else None

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM output_reviews
            WHERE project_id = ? AND output_index = ?
            """,
            (project_id, output_index),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO output_reviews (
                id, project_id, output_index, review_status, user_note,
                quality_score_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, output_index) DO UPDATE SET
                review_status = excluded.review_status,
                user_note = excluded.user_note,
                quality_score_json = COALESCE(excluded.quality_score_json, output_reviews.quality_score_json),
                updated_at = excluded.updated_at
            """,
            (
                review_id,
                project_id,
                output_index,
                review_status,
                user_note,
                quality_score_json,
                created_at,
                now,
            ),
        )

    review = get_output_review(project_id, output_index)
    assert review is not None
    return review


def update_output_review(
    project_id: str,
    output_index: int,
    review_status: str,
    user_note: str | None = None,
) -> dict[str, Any]:
    existing = get_output_review(project_id, output_index)
    quality_score = existing.get("quality_score") if existing else None
    return upsert_output_review(
        project_id=project_id,
        output_index=output_index,
        review_status=review_status,
        user_note=user_note,
        quality_score=quality_score,
    )


def get_output_review(project_id: str, output_index: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM output_reviews
            WHERE project_id = ? AND output_index = ?
            """,
            (project_id, output_index),
        ).fetchone()
    return _row_to_output_review(row) if row else None


def list_output_reviews(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM output_reviews
            WHERE project_id = ?
            ORDER BY output_index ASC
            """,
            (project_id,),
        ).fetchall()
    return [_row_to_output_review(row) for row in rows]


def upsert_output_content_item(item: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    project_id = str(item["project_id"])
    output_index = int(item["output_index"])
    content_id = str(item.get("id") or _output_content_item_id(project_id, output_index))
    hashtags = item.get("hashtags") or []
    hashtags_json = json.dumps(list(hashtags), ensure_ascii=False)

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM output_content_items
            WHERE project_id = ? AND output_index = ?
            """,
            (project_id, output_index),
        ).fetchone()
        created_at = str(item.get("created_at") or (existing["created_at"] if existing else now))
        updated_at = now
        conn.execute(
            """
            INSERT INTO output_content_items (
                id, project_id, output_index, video_path, hook, caption,
                hashtags_json, cta, variant_style_id, timeline_template_id,
                publish_status, platform, user_note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, output_index) DO UPDATE SET
                video_path = excluded.video_path,
                hook = excluded.hook,
                caption = excluded.caption,
                hashtags_json = excluded.hashtags_json,
                cta = excluded.cta,
                variant_style_id = excluded.variant_style_id,
                timeline_template_id = excluded.timeline_template_id,
                publish_status = excluded.publish_status,
                platform = excluded.platform,
                user_note = excluded.user_note,
                updated_at = excluded.updated_at
            """,
            (
                content_id,
                project_id,
                output_index,
                str(item["video_path"]),
                item.get("hook"),
                str(item["caption"]),
                hashtags_json,
                item.get("cta"),
                item.get("variant_style_id"),
                item.get("timeline_template_id"),
                str(item.get("publish_status") or "draft"),
                item.get("platform"),
                item.get("user_note"),
                created_at,
                updated_at,
            ),
        )

    content_item = get_output_content_item(project_id, output_index)
    assert content_item is not None
    return content_item


def get_output_content_item(project_id: str, output_index: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM output_content_items
            WHERE project_id = ? AND output_index = ?
            """,
            (project_id, output_index),
        ).fetchone()
    return _row_to_output_content_item(row) if row else None


def list_output_content_items(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM output_content_items
            WHERE project_id = ?
            ORDER BY output_index ASC
            """,
            (project_id,),
        ).fetchall()
    return [_row_to_output_content_item(row) for row in rows]


def update_output_content_item(
    project_id: str,
    output_index: int,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    allowed = {
        "video_path",
        "hook",
        "caption",
        "hashtags",
        "cta",
        "variant_style_id",
        "timeline_template_id",
        "publish_status",
        "platform",
        "user_note",
    }
    fields = {key: value for key, value in updates.items() if key in allowed}
    if not fields:
        return get_output_content_item(project_id, output_index)

    if "hashtags" in fields:
        fields["hashtags_json"] = json.dumps(fields.pop("hashtags") or [], ensure_ascii=False)

    fields["updated_at"] = _now()
    assignments = []
    values: list[Any] = []
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        values.append(value)
    values.extend([project_id, output_index])

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE output_content_items
            SET {", ".join(assignments)}
            WHERE project_id = ? AND output_index = ?
            """,
            values,
        )

    return get_output_content_item(project_id, output_index)


def upsert_source_media_review(
    project_id: str,
    media_path: str,
    review_status: str,
    user_note: str | None = None,
) -> dict[str, Any]:
    now = _now()
    review_id = _source_media_review_id(project_id, media_path)
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM source_media_reviews
            WHERE project_id = ? AND media_path = ?
            """,
            (project_id, media_path),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO source_media_reviews (
                id, project_id, media_path, review_status, user_note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, media_path) DO UPDATE SET
                review_status = excluded.review_status,
                user_note = excluded.user_note,
                updated_at = excluded.updated_at
            """,
            (review_id, project_id, media_path, review_status, user_note, created_at, now),
        )
    review = get_source_media_review(project_id, media_path)
    assert review is not None
    return review


def get_source_media_review(project_id: str, media_path: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM source_media_reviews
            WHERE project_id = ? AND media_path = ?
            """,
            (project_id, media_path),
        ).fetchone()
    return dict(row) if row else None


def list_source_media_reviews(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM source_media_reviews
            WHERE project_id = ?
            ORDER BY updated_at DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_segment_review(
    project_id: str,
    segment_id: str,
    source_path: str,
    start: float,
    end: float,
    review_status: str,
    user_note: str | None = None,
) -> dict[str, Any]:
    now = _now()
    review_id = _segment_review_id(project_id, segment_id)
    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT created_at
            FROM segment_reviews
            WHERE project_id = ? AND segment_id = ?
            """,
            (project_id, segment_id),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO segment_reviews (
                id, project_id, segment_id, source_path, start, end,
                review_status, user_note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, segment_id) DO UPDATE SET
                source_path = excluded.source_path,
                start = excluded.start,
                end = excluded.end,
                review_status = excluded.review_status,
                user_note = excluded.user_note,
                updated_at = excluded.updated_at
            """,
            (
                review_id,
                project_id,
                segment_id,
                source_path,
                float(start),
                float(end),
                review_status,
                user_note,
                created_at,
                now,
            ),
        )
    review = get_segment_review(project_id, segment_id)
    assert review is not None
    return review


def get_segment_review(project_id: str, segment_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM segment_reviews
            WHERE project_id = ? AND segment_id = ?
            """,
            (project_id, segment_id),
        ).fetchone()
    return dict(row) if row else None


def list_segment_reviews(project_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM segment_reviews
            WHERE project_id = ?
            ORDER BY source_path ASC, start ASC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_app_settings() -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", ("default",)).fetchone()
    if not row:
        return {}
    return json.loads(row["value_json"] or "{}")


def update_app_settings(settings: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    payload = json.dumps(settings, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            ("default", payload, now),
        )
    return get_app_settings()


def is_known_output_path(path: str) -> bool:
    target = Path(path).expanduser().resolve()
    with get_connection() as conn:
        rows = conn.execute("SELECT results_json FROM jobs WHERE results_json IS NOT NULL").fetchall()
        try:
            review_rows = conn.execute("SELECT video_path FROM subtitle_review_documents").fetchall()
        except sqlite3.OperationalError:
            review_rows = []

    for row in rows:
        try:
            payload = json.loads(row["results_json"] or '{"outputs": []}')
        except json.JSONDecodeError:
            continue
        for output in payload.get("outputs", []):
            if not isinstance(output, dict):
                continue
            for key in ("path", "visual_video"):
                value = output.get(key)
                if not value:
                    continue
                try:
                    if Path(value).expanduser().resolve() == target:
                        return True
                except OSError:
                    continue
    for row in review_rows:
        try:
            if Path(row["video_path"]).expanduser().resolve() == target:
                return True
        except OSError:
            continue
    return False


def is_known_job_artifact_path(path: str) -> bool:
    target = Path(path).expanduser().resolve()
    with get_connection() as conn:
        rows = conn.execute("SELECT results_json FROM jobs WHERE results_json IS NOT NULL").fetchall()
    for row in rows:
        try:
            payload = json.loads(row["results_json"] or "{}")
        except json.JSONDecodeError:
            continue
        for value in _walk_json_values(payload):
            if not isinstance(value, str) or not value:
                continue
            try:
                if Path(value).expanduser().resolve() == target:
                    return True
            except OSError:
                continue
    return False


def _walk_json_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_json_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json_values(item)
    else:
        yield value


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["config"] = json.loads(data.pop("config_json"))
    data["latest_script"] = _loads_optional_json(data.pop("latest_script_json", None))
    data["custom_script"] = _loads_optional_json(data.pop("custom_script_json", None))
    return data


def _row_to_job(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["preview_only"] = bool(data["preview_only"])
    data["results"] = json.loads(data.pop("results_json") or '{"outputs": []}')
    return data


def _row_to_output_review(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["quality_score"] = _loads_optional_json(data.pop("quality_score_json", None))
    return data


def _row_to_output_content_item(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["hashtags"] = json.loads(data.pop("hashtags_json") or "[]")
    return data


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing_columns = {row["name"] for row in rows}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _update_project_script(project_id: str, column: str, script: dict[str, Any]) -> None:
    if column not in {"latest_script_json", "custom_script_json"}:
        raise ValueError(f"Unsupported project script column: {column}")

    with get_connection() as conn:
        conn.execute(
            f"UPDATE projects SET {column} = ?, updated_at = ? WHERE project_id = ?",
            (json.dumps(script, ensure_ascii=False), _now(), project_id),
        )


def _loads_optional_json(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _output_review_id(project_id: str, output_index: int) -> str:
    return f"{project_id}:{output_index}"


def _output_content_item_id(project_id: str, output_index: int) -> str:
    return f"{project_id}:content:{output_index}"


def _source_media_review_id(project_id: str, media_path: str) -> str:
    return f"{project_id}:media:{media_path}"


def _segment_review_id(project_id: str, segment_id: str) -> str:
    return f"{project_id}:segment:{segment_id}"
