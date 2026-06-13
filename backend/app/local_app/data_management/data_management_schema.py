from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DataCategory(str, Enum):
    config = "config"
    database = "database"
    projects = "projects"
    outputs = "outputs"
    exports = "exports"
    subtitles = "subtitles"
    logs = "logs"
    cache = "cache"
    temp = "temp"
    backups = "backups"
    frontend = "frontend"


class StorageItem(BaseModel):
    path: str
    category: DataCategory
    exists: bool
    size_bytes: int = 0
    file_count: int = 0
    folder_count: int = 0
    last_modified: str | None = None
    safe_to_cleanup: bool = False
    description: str | None = None


class StorageUsageReport(BaseModel):
    total_size_bytes: int
    items: list[StorageItem]
    warnings: list[str] = Field(default_factory=list)


class BackupRequest(BaseModel):
    include_config: bool = True
    include_database: bool = True
    include_projects: bool = True
    include_outputs: bool = False
    include_exports: bool = True
    include_subtitles: bool = True
    include_logs: bool = False
    backup_name: str | None = None
    backup_folder: str | None = None


class BackupFileItem(BaseModel):
    path: str
    size_bytes: int


class BackupManifest(BaseModel):
    app_name: str = "Auto Tool Studio"
    version: str
    created_at: str
    included_categories: list[DataCategory]
    files: list[BackupFileItem]
    notes: list[str] = Field(default_factory=list)


class BackupResult(BaseModel):
    success: bool
    backup_path: str | None = None
    manifest_path: str | None = None
    size_bytes: int = 0
    included_categories: list[DataCategory] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BackupListItem(BaseModel):
    path: str
    manifest_path: str | None = None
    size_bytes: int = 0
    created_at: str | None = None
    included_categories: list[DataCategory] = Field(default_factory=list)


class BackupListResponse(BaseModel):
    success: bool = True
    items: list[BackupListItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BackupInspectRequest(BaseModel):
    backup_path: str


class BackupInspectResult(BaseModel):
    success: bool
    backup_path: str
    manifest: dict[str, Any] | None = None
    included_categories: list[DataCategory] = Field(default_factory=list)
    file_count: int = 0
    size_bytes: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RestoreRequest(BaseModel):
    backup_path: str
    restore_config: bool = True
    restore_database: bool = True
    restore_projects: bool = True
    restore_outputs: bool = False
    restore_exports: bool = True
    restore_subtitles: bool = True
    restore_logs: bool = False
    create_pre_restore_backup: bool = True
    overwrite_existing: bool = False


class RestoreResult(BaseModel):
    success: bool
    restored_categories: list[DataCategory] = Field(default_factory=list)
    pre_restore_backup_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CleanupTarget(str, Enum):
    launcher_logs = "launcher_logs"
    debug_logs = "debug_logs"
    temp_files = "temp_files"
    cache_files = "cache_files"
    preview_frames = "preview_frames"
    failed_partial_renders = "failed_partial_renders"
    old_exports = "old_exports"


class CleanupRequest(BaseModel):
    targets: list[CleanupTarget]
    older_than_days: int = Field(default=14, ge=0)
    dry_run: bool = True
    confirm_delete: bool = False


class CleanupPreviewItem(BaseModel):
    path: str
    target: CleanupTarget
    size_bytes: int
    file_count: int
    reason: str


class CleanupResult(BaseModel):
    success: bool
    dry_run: bool
    deleted_size_bytes: int = 0
    deleted_file_count: int = 0
    preview_items: list[CleanupPreviewItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class StorageUsageApiResponse(BaseModel):
    success: bool
    data: StorageUsageReport
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

