from pathlib import Path

from fastapi.testclient import TestClient

import app.api as api_module
from app.api import create_app


def test_data_management_api_returns_wrapped_responses(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "local_app_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(api_module.database, "DB_PATH", tmp_path / "data" / "autotool.db")
    client = TestClient(create_app())

    usage = client.get("/api/local-app/storage-usage")
    assert usage.status_code == 200
    assert usage.json()["success"] is True
    assert "data" in usage.json()

    backup = client.post("/api/local-app/backup", json={"include_database": False, "include_projects": False})
    assert backup.status_code == 200
    assert backup.json()["success"] is True

    listed = client.get("/api/local-app/backups")
    assert listed.status_code == 200
    assert listed.json()["items"]

    preview = client.post(
        "/api/local-app/cleanup/preview",
        json={"targets": ["launcher_logs"], "older_than_days": 0, "dry_run": True, "confirm_delete": False},
    )
    assert preview.status_code == 200
    assert preview.json()["dry_run"] is True

