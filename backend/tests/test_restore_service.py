from pathlib import Path
from zipfile import ZipFile

from app.local_app.data_management.backup_service import BackupService
from app.local_app.data_management.data_management_schema import BackupRequest, RestoreRequest
from app.local_app.data_management.restore_service import RestoreService


def test_restore_inspect_reads_manifest(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "local_app_config.json").write_text('{"ok": true}', encoding="utf-8")
    backup = BackupService(tmp_path).create_backup(
        BackupRequest(include_database=False, include_projects=False, include_exports=False, include_subtitles=False)
    )

    inspected = RestoreService(tmp_path).inspect_backup(backup.backup_path or "")

    assert inspected.success
    assert inspected.manifest
    assert inspected.file_count >= 1


def test_restore_blocks_zip_slip(tmp_path: Path):
    zip_path = tmp_path / "bad.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("../bad.txt", "bad")

    inspected = RestoreService(tmp_path).inspect_backup(str(zip_path))

    assert not inspected.success
    assert inspected.errors


def test_restore_creates_pre_restore_backup_and_does_not_overwrite_by_default(tmp_path: Path):
    config = tmp_path / "config"
    config.mkdir()
    target = config / "local_app_config.json"
    target.write_text("old", encoding="utf-8")
    backup = BackupService(tmp_path).create_backup(
        BackupRequest(include_database=False, include_projects=False, include_exports=False, include_subtitles=False)
    )
    target.write_text("current", encoding="utf-8")

    result = RestoreService(tmp_path).restore_backup(
        RestoreRequest(backup_path=backup.backup_path or "", create_pre_restore_backup=True, overwrite_existing=False)
    )

    assert result.success
    assert result.pre_restore_backup_path
    assert target.read_text(encoding="utf-8") == "current"
    assert any("Bỏ qua file đã tồn tại" in warning for warning in result.warnings)

