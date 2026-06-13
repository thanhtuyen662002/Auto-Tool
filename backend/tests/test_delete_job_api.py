from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from fastapi.testclient import TestClient

from app import database
from app.api import create_app


def test_delete_job_flow(tmp_path: Path, monkeypatch):
    # Setup temporary database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool_test.db")
    database.init_db()

    # Create dummy project
    project_id = "test-project-delete"
    database.create_project(project_id, {"project_name": "Delete Test Project"})

    # Create dummy job
    job_id = "test-job-delete"
    database.create_job(job_id, project_id, preview_only=False, total_outputs=3)

    # Insert dependent rows in job_logs
    database.add_job_log(job_id, "INFO", "Bắt đầu tác vụ test")
    database.add_job_log(job_id, "WARNING", "Cảnh báo test")

    # Insert dependent rows in subtitle_review_documents and subtitle_review_lines manually
    now_str = database._now()
    doc_id = "doc-test-1"
    with database.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO subtitle_review_documents (
                id, project_id, job_id, video_id, video_path, source_language, target_language, 
                translated_srt_path, status, line_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, project_id, job_id, "video-1", "path/to/video-1.mp4", "zh", "vi", 
             "path/to/translated.srt", "pending", 2, now_str, now_str)
        )

        
        conn.execute(
            """
            INSERT INTO subtitle_review_lines (
                id, document_id, line_index, start_ms, end_ms, translated_text, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("line-1", doc_id, 0, 0, 1000, "Chào mọi người", "pending", now_str, now_str)
        )
        
        conn.execute(
            """
            INSERT INTO silent_visual_tag_reports (
                id, job_id, project_id, video_path, report_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("tag-report-1", job_id, project_id, "path/to/video-1.mp4", "{}", now_str, now_str)
        )

    # Verify rows exist before delete
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) as count FROM jobs WHERE job_id = ?", (job_id,)).fetchone()["count"] == 1
        assert conn.execute("SELECT COUNT(*) as count FROM job_logs WHERE job_id = ?", (job_id,)).fetchone()["count"] == 2
        assert conn.execute("SELECT COUNT(*) as count FROM subtitle_review_documents WHERE job_id = ?", (job_id,)).fetchone()["count"] == 1
        assert conn.execute("SELECT COUNT(*) as count FROM subtitle_review_lines WHERE document_id = ?", (doc_id,)).fetchone()["count"] == 1
        assert conn.execute("SELECT COUNT(*) as count FROM silent_visual_tag_reports WHERE job_id = ?", (job_id,)).fetchone()["count"] == 1

    # Call delete endpoint
    client = TestClient(create_app())
    response = client.delete(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json() == {"success": True, "job_id": job_id}

    # Verify rows are deleted (cascade cleanup test)
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) as count FROM jobs WHERE job_id = ?", (job_id,)).fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) as count FROM job_logs WHERE job_id = ?", (job_id,)).fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) as count FROM subtitle_review_documents WHERE job_id = ?", (job_id,)).fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) as count FROM subtitle_review_lines WHERE document_id = ?", (doc_id,)).fetchone()["count"] == 0
        assert conn.execute("SELECT COUNT(*) as count FROM silent_visual_tag_reports WHERE job_id = ?", (job_id,)).fetchone()["count"] == 0

    # Call delete endpoint again and assert 404
    err_response = client.delete(f"/api/jobs/{job_id}")
    assert err_response.status_code == 404
    assert err_response.json()["detail"] == "Job not found"
