from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app import database
from app.local_app.data_management.data_management_schema import DataCategory, StorageItem, StorageUsageReport
from app.utils.app_paths import app_data_dir


class StorageUsageService:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()

    def build_report(self) -> StorageUsageReport:
        warnings: list[str] = []
        items = [
            self.scan_item(self.project_root / "config", DataCategory.config, description="Cài đặt local, recent folders."),
            self.scan_item(database.DB_PATH, DataCategory.database, description="SQLite database/project metadata."),
            self.scan_item(self.project_root / "examples", DataCategory.projects, description="Example/project metadata local."),
            self.scan_item(self.project_root / "outputs", DataCategory.outputs, description="Output video folder mặc định."),
            self.scan_item(self.project_root / "examples" / "outputs", DataCategory.outputs, description="Example output folder."),
            self.scan_item(self.project_root / "logs", DataCategory.logs, safe_to_cleanup=True, description="Log của launcher/render/debug."),
            self.scan_item(self.project_root / "cache", DataCategory.cache, safe_to_cleanup=True, description="Cache local trong project."),
            self.scan_item(app_data_dir() / "cache", DataCategory.cache, safe_to_cleanup=True, description="Cache trong app data."),
            self.scan_item(self.project_root / "temp", DataCategory.temp, safe_to_cleanup=True, description="File tạm trong project."),
            self.scan_item(self.project_root / "backups", DataCategory.backups, description="Backup local đã tạo."),
            self.scan_item(self.project_root / "frontend" / "dist", DataCategory.frontend, description="Frontend production build."),
        ]
        total = sum(item.size_bytes for item in items)
        return StorageUsageReport(total_size_bytes=total, items=items, warnings=warnings)

    def scan_item(
        self,
        path: str | Path,
        category: DataCategory,
        safe_to_cleanup: bool = False,
        description: str | None = None,
    ) -> StorageItem:
        target = Path(path).expanduser()
        exists = target.exists()
        size = files = folders = 0
        modified = None
        if exists:
            try:
                size, files, folders = self.get_folder_size(target)
                modified = datetime.fromtimestamp(target.stat().st_mtime).replace(microsecond=0).isoformat()
            except OSError:
                size = files = folders = 0
        return StorageItem(
            path=str(target),
            category=category,
            exists=exists,
            size_bytes=size,
            file_count=files,
            folder_count=folders,
            last_modified=modified,
            safe_to_cleanup=safe_to_cleanup,
            description=description,
        )

    def get_folder_size(self, path: str | Path) -> tuple[int, int, int]:
        target = Path(path)
        if not target.exists():
            return 0, 0, 0
        if target.is_file():
            return target.stat().st_size, 1, 0
        total_size = 0
        file_count = 0
        folder_count = 0
        for item in target.rglob("*"):
            try:
                if item.is_symlink():
                    continue
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
                elif item.is_dir():
                    folder_count += 1
            except OSError:
                continue
        return total_size, file_count, folder_count

