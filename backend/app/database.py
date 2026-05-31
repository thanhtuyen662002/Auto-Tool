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
            """
        )
        _ensure_column(conn, "projects", "latest_script_json", "TEXT")
        _ensure_column(conn, "projects", "custom_script_json", "TEXT")


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
    return False


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
