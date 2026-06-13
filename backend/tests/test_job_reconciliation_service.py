import json
from pathlib import Path

from app import database
from app.modules.job_recovery.job_reconciliation_service import JobReconciliationService


def test_reconcile_marks_existing_non_video_output_complete(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "autotool.db")
    database.init_db()
    database.create_project("project-1", {"project_name": "demo"})
    database.create_job("job-1", "project-1", preview_only=False, total_outputs=2)
    output = tmp_path / "output.txt"
    output.write_text("ok", encoding="utf-8")
    database.update_job(
        "job-1",
        status="recoverable",
        completed_outputs=1,
        output_folder=str(tmp_path),
        results_json=json.dumps({"outputs": [{"index": 1, "path": str(output), "status": "success"}]}),
    )

    result = JobReconciliationService().reconcile_job_outputs("job-1")

    assert result["completed_items"] == 1
    assert result["interrupted_items"] == 1
    assert result["outputs"][0]["recovery_status"] == "rendered"
    assert (tmp_path / "recovery_reconciliation.json").exists()

