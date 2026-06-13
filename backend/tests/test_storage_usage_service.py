from pathlib import Path

from app.local_app.data_management.data_management_schema import DataCategory
from app.local_app.data_management.storage_usage_service import StorageUsageService


def test_storage_usage_does_not_crash_when_folders_are_missing(tmp_path: Path):
    report = StorageUsageService(tmp_path).build_report()

    assert report.total_size_bytes >= 0
    assert any(item.category == DataCategory.config for item in report.items)
    assert any(not item.exists for item in report.items)


def test_storage_usage_counts_files(tmp_path: Path):
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / "one.log").write_text("abc", encoding="utf-8")

    item = StorageUsageService(tmp_path).scan_item(folder, DataCategory.logs)

    assert item.exists
    assert item.size_bytes == 3
    assert item.file_count == 1

