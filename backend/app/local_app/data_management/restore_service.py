from __future__ import annotations

import json
import zipfile
from pathlib import Path

from app.local_app.data_management.backup_service import BackupService
from app.local_app.data_management.data_management_schema import (
    BackupInspectResult,
    BackupRequest,
    DataCategory,
    RestoreRequest,
    RestoreResult,
)
from app.local_app.data_management.data_safety_service import DataSafetyService
from app.utils.app_paths import app_data_dir


class RestoreService:
    def __init__(
        self,
        project_root: Path | None = None,
        safety: DataSafetyService | None = None,
        backup_service: BackupService | None = None,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.app_data_root = app_data_dir()
        self.safety = safety or DataSafetyService(self.project_root)
        self.backup_service = backup_service or BackupService(self.project_root, self.safety)

    def inspect_backup(self, backup_path: str) -> BackupInspectResult:
        path = Path(backup_path).expanduser().resolve()
        warnings: list[str] = []
        errors: list[str] = []
        if not path.exists() or path.suffix.lower() != ".zip":
            return BackupInspectResult(success=False, backup_path=str(path), errors=[f"Backup zip không tồn tại: {path}"])
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                for name in names:
                    if not self.safety.prevent_zip_slip(name):
                        errors.append(f"Backup chứa path không an toàn: {name}")
                manifest = self._read_manifest(archive)
                categories = _categories_from_manifest_or_names(manifest, names)
                size = sum(info.file_size for info in archive.infolist() if not info.is_dir())
        except (OSError, zipfile.BadZipFile) as exc:
            return BackupInspectResult(success=False, backup_path=str(path), errors=[f"Không thể đọc backup: {exc}"])
        return BackupInspectResult(
            success=not errors,
            backup_path=str(path),
            manifest=manifest,
            included_categories=categories,
            file_count=len([name for name in names if not name.endswith("/")]),
            size_bytes=size,
            warnings=warnings,
            errors=errors,
        )

    def restore_backup(self, request: RestoreRequest) -> RestoreResult:
        inspect = self.inspect_backup(request.backup_path)
        warnings = list(inspect.warnings)
        errors = list(inspect.errors)
        pre_restore_backup_path = None
        restored: set[DataCategory] = set()
        if not inspect.success:
            return RestoreResult(success=False, warnings=warnings, errors=errors)

        requested = _restore_categories(request)
        if request.create_pre_restore_backup:
            backup_result = self.backup_service.create_backup(
                BackupRequest(
                    include_config=request.restore_config,
                    include_database=request.restore_database,
                    include_projects=request.restore_projects,
                    include_outputs=request.restore_outputs,
                    include_exports=request.restore_exports,
                    include_subtitles=request.restore_subtitles,
                    include_logs=request.restore_logs,
                    backup_name="pre_restore_backup",
                )
            )
            pre_restore_backup_path = backup_result.backup_path
            warnings.extend(backup_result.warnings)
            if not backup_result.success:
                errors.extend([f"Không thể tạo pre-restore backup: {item}" for item in backup_result.errors])
                return RestoreResult(success=False, pre_restore_backup_path=pre_restore_backup_path, warnings=warnings, errors=errors)

        backup_path = Path(request.backup_path).expanduser().resolve()
        try:
            with zipfile.ZipFile(backup_path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.filename == "backup_manifest.json":
                        continue
                    if not self.safety.prevent_zip_slip(info.filename):
                        errors.append(f"Đã chặn path không an toàn: {info.filename}")
                        continue
                    category = _category_for_member(info.filename)
                    if category not in requested:
                        continue
                    target = self._target_path(info.filename)
                    if self.safety.is_sensitive_file(target):
                        warnings.append(f"Không restore file nhạy cảm: {info.filename}")
                        continue
                    if target.exists() and not request.overwrite_existing:
                        warnings.append(f"Bỏ qua file đã tồn tại: {target}")
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as destination:
                        destination.write(source.read())
                    restored.add(category)
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"Restore thất bại: {exc}")

        return RestoreResult(
            success=not errors,
            restored_categories=sorted(restored, key=lambda item: item.value),
            pre_restore_backup_path=pre_restore_backup_path,
            warnings=warnings,
            errors=errors,
        )

    @staticmethod
    def _read_manifest(archive: zipfile.ZipFile) -> dict | None:
        try:
            with archive.open("backup_manifest.json") as file:
                return json.loads(file.read().decode("utf-8"))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _target_path(self, member_name: str) -> Path:
        normalized = member_name.replace("\\", "/")
        if normalized.startswith("app_data/"):
            target = (self.app_data_root / normalized.removeprefix("app_data/")).resolve()
            target.relative_to(self.app_data_root)
            return target
        target = (self.project_root / normalized).resolve()
        target.relative_to(self.project_root)
        return target


def _restore_categories(request: RestoreRequest) -> set[DataCategory]:
    categories: set[DataCategory] = set()
    if request.restore_config:
        categories.add(DataCategory.config)
    if request.restore_database or request.restore_projects:
        categories.add(DataCategory.database)
    if request.restore_projects:
        categories.add(DataCategory.projects)
    if request.restore_outputs:
        categories.add(DataCategory.outputs)
    if request.restore_exports:
        categories.add(DataCategory.exports)
    if request.restore_subtitles:
        categories.add(DataCategory.subtitles)
    if request.restore_logs:
        categories.add(DataCategory.logs)
    return categories


def _categories_from_manifest_or_names(manifest: dict | None, names: list[str]) -> list[DataCategory]:
    if manifest:
        categories = []
        for item in manifest.get("included_categories", []):
            try:
                categories.append(DataCategory(item))
            except ValueError:
                continue
        if categories:
            return sorted(set(categories), key=lambda item: item.value)
    return sorted({_category_for_member(name) for name in names if not name.endswith("/")}, key=lambda item: item.value)


def _category_for_member(name: str) -> DataCategory:
    normalized = name.replace("\\", "/")
    suffix = Path(normalized).suffix.lower()
    if normalized.startswith("config/"):
        return DataCategory.config
    if normalized.endswith(".db") or normalized.startswith("app_data/data/") or normalized.startswith("backend/data/"):
        return DataCategory.database
    if normalized.startswith("examples/") and "/outputs/" not in normalized:
        return DataCategory.projects
    if "/export_pack/" in normalized or normalized.endswith("/export_pack"):
        return DataCategory.exports
    if suffix in {".srt", ".ass", ".vtt"}:
        return DataCategory.subtitles
    if normalized.startswith("logs/"):
        return DataCategory.logs
    if normalized.startswith("outputs/") or normalized.startswith("examples/outputs/"):
        return DataCategory.outputs
    return DataCategory.projects

