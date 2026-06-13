from pathlib import Path
from zipfile import ZipFile

from app.local_app.data_management.backup_service import BackupService
from app.local_app.data_management.data_management_schema import BackupRequest, DataCategory


def test_backup_creates_zip_and_manifest_excluding_sensitive_files(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "local_app_config.json").write_text("{}", encoding="utf-8")
    (config / ".env").write_text("SECRET=1", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "skip.py").write_text("x", encoding="utf-8")

    result = BackupService(tmp_path).create_backup(
        BackupRequest(include_database=False, include_projects=False, include_exports=False, include_subtitles=False)
    )

    assert result.success
    assert result.backup_path
    assert result.manifest_path and Path(result.manifest_path).exists()
    assert DataCategory.config in result.included_categories
    with ZipFile(result.backup_path) as archive:
        names = set(archive.namelist())
    assert "config/local_app_config.json" in names
    assert "config/.env" not in names
    assert ".venv/skip.py" not in names
    assert "backup_manifest.json" in names


def test_list_backups_reads_manifest(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "local_app_config.json").write_text("{}", encoding="utf-8")
    service = BackupService(tmp_path)
    service.create_backup(BackupRequest(include_database=False, include_projects=False, include_exports=False, include_subtitles=False))

    response = service.list_backups()

    assert response.success
    assert len(response.items) == 1
