from __future__ import annotations

from pathlib import Path

from app import database


def test_add_job_log_initializes_missing_log_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool_test.db")

    database.add_job_log("job-with-late-db", "warning", "Log được ghi sau khi DB chưa init.")

    logs = database.get_job_logs("job-with-late-db")
    assert len(logs) == 1
    assert logs[0]["level"] == "warning"
    assert logs[0]["message"] == "Log được ghi sau khi DB chưa init."


def test_job_logs_can_return_latest_slice_with_total_meta(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool_test.db")
    job_id = "job-with-many-logs"
    for index in range(5):
        database.add_job_log(job_id, "info", f"log line {index}")

    logs, total, truncated = database.get_job_logs_with_meta(job_id, limit=2)

    assert total == 5
    assert truncated is True
    assert [item["message"] for item in logs] == ["log line 3", "log line 4"]


def test_job_logs_limit_zero_returns_complete_history(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool_test.db")
    job_id = "job-with-complete-logs"
    for index in range(5):
        database.add_job_log(job_id, "info", f"log line {index}")

    logs, total, truncated = database.get_job_logs_with_meta(job_id, limit=0)

    assert total == 5
    assert truncated is False
    assert [item["message"] for item in logs] == [f"log line {index}" for index in range(5)]
