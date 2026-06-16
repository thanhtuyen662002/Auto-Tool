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
