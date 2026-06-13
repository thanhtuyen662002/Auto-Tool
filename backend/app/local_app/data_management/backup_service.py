from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from app import database
from app.local_app.data_management.data_management_schema import (
    BackupFileItem,
    BackupListItem,
    BackupListResponse,
    BackupManifest,
    BackupRequest,
    BackupResult,
    DataCategory,
)
from app.local_app.data_management.data_safety_service import DataSafetyService
from app.utils.app_paths import app_data_dir
from app.version import APP_VERSION


EXCLUDED_DIR_NAMES = {".venv", "node_modules", "__pycache__", ".cache", ".git"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class BackupService:
    def __init__(self, project_root: Path | None = None, safety: DataSafetyService | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.app_data_root = app_data_dir()
        self.safety = safety or DataSafetyService(self.project_root)

    def create_backup(self, request: BackupRequest) -> BackupResult:
        warnings: list[str] = []
        errors: list[str] = []
        backup_dir = self._backup_dir(request.backup_folder)
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = _safe_backup_name(request.backup_name) or f"auto_tool_backup_{timestamp}"
        backup_path = backup_dir / f"{backup_name}.zip"
        manifest_path = backup_dir / f"{backup_name}.manifest.json"
        if backup_path.exists():
            backup_path = backup_dir / f"{backup_name}_{timestamp}.zip"
            manifest_path = backup_path.with_suffix(".manifest.json")

        included = self._collect_files(request, backup_path, warnings)
        if not included:
            errors.append("Không có file hợp lệ để backup.")
            return BackupResult(success=False, errors=errors, warnings=warnings)

        files = [BackupFileItem(path=arcname, size_bytes=path.stat().st_size) for path, arcname, _ in included]
        categories = sorted({category for _, _, category in included}, key=lambda item: item.value)
        manifest = BackupManifest(
            version=APP_VERSION,
            created_at=datetime.now().replace(microsecond=0).isoformat(),
            included_categories=categories,
            files=files,
            notes=[
                "Source videos and external music folders are not included by default.",
                ".env, keys, credentials, node_modules and .venv are excluded.",
            ],
        )
        manifest_payload = manifest.model_dump(mode="json")
        try:
            with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path, arcname, _ in included:
                    archive.write(file_path, arcname)
                archive.writestr("backup_manifest.json", json.dumps(manifest_payload, ensure_ascii=False, indent=2))
            manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            errors.append(f"Không thể tạo backup: {exc}")
            return BackupResult(success=False, errors=errors, warnings=warnings)

        return BackupResult(
            success=True,
            backup_path=str(backup_path),
            manifest_path=str(manifest_path),
            size_bytes=backup_path.stat().st_size,
            included_categories=categories,
            warnings=warnings,
            errors=errors,
        )

    def list_backups(self, backup_folder: str | None = None) -> BackupListResponse:
        backup_dir = self._backup_dir(backup_folder)
        items: list[BackupListItem] = []
        if not backup_dir.exists():
            return BackupListResponse(items=items)
        for path in sorted(backup_dir.glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True):
            manifest_path = path.with_suffix(".manifest.json")
            categories: list[DataCategory] = []
            created_at = datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat()
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    created_at = manifest.get("created_at") or created_at
                    categories = _parse_categories(manifest.get("included_categories", []))
                except (OSError, ValueError, TypeError):
                    categories = []
            items.append(
                BackupListItem(
                    path=str(path),
                    manifest_path=str(manifest_path) if manifest_path.exists() else None,
                    size_bytes=path.stat().st_size,
                    created_at=created_at,
                    included_categories=categories,
                )
            )
        return BackupListResponse(items=items)

    def build_backup_manifest(
        self,
        backup_path: str,
        included_files: list[str],
        request: BackupRequest,
    ) -> dict:
        categories = self._requested_categories(request)
        return BackupManifest(
            version=APP_VERSION,
            created_at=datetime.now().replace(microsecond=0).isoformat(),
            included_categories=categories,
            files=[BackupFileItem(path=item, size_bytes=0) for item in included_files],
        ).model_dump(mode="json")

    def _collect_files(
        self,
        request: BackupRequest,
        backup_path: Path,
        warnings: list[str],
    ) -> list[tuple[Path, str, DataCategory]]:
        candidates: list[tuple[Path, str, DataCategory]] = []
        requested = self._requested_categories(request)
        for category in requested:
            for path, arcname in self._category_paths(category):
                for file_path in self._iter_files(path):
                    if file_path.resolve() == backup_path.resolve():
                        continue
                    if category == DataCategory.projects and _is_under(file_path, self.project_root / "examples" / "outputs"):
                        continue
                    if self._should_exclude(file_path, warnings):
                        continue
                    try:
                        rel_arcname = self._archive_name(file_path, arcname)
                    except ValueError as exc:
                        warnings.append(str(exc))
                        continue
                    candidates.append((file_path, rel_arcname, category))
        deduped: dict[str, tuple[Path, str, DataCategory]] = {}
        for item in candidates:
            deduped[item[1]] = item
        return list(deduped.values())

    def _requested_categories(self, request: BackupRequest) -> list[DataCategory]:
        categories: list[DataCategory] = []
        if request.include_config:
            categories.append(DataCategory.config)
        if request.include_database or request.include_projects:
            categories.append(DataCategory.database)
        if request.include_projects:
            categories.append(DataCategory.projects)
        if request.include_outputs:
            categories.append(DataCategory.outputs)
        if request.include_exports:
            categories.append(DataCategory.exports)
        if request.include_subtitles:
            categories.append(DataCategory.subtitles)
        if request.include_logs:
            categories.append(DataCategory.logs)
        return categories

    def _category_paths(self, category: DataCategory) -> list[tuple[Path, str]]:
        if category == DataCategory.config:
            return [(self.project_root / "config", "config")]
        if category == DataCategory.database:
            return [(database.DB_PATH, self._arc_prefix_for(database.DB_PATH))]
        if category == DataCategory.projects:
            return [(self.project_root / "examples", "examples")]
        if category == DataCategory.outputs:
            return [(self.project_root / "outputs", "outputs"), (self.project_root / "examples" / "outputs", "examples/outputs")]
        if category == DataCategory.exports:
            return [(path, self._relative_arcname(path)) for path in self._find_export_pack_dirs()]
        if category == DataCategory.subtitles:
            return [(path, self._relative_arcname(path)) for path in self._find_subtitle_files()]
        if category == DataCategory.logs:
            return [(self.project_root / "logs", "logs")]
        return []

    def _iter_files(self, path: Path) -> list[Path]:
        if not path.exists():
            return []
        if path.is_file():
            return [path]
        return [item for item in path.rglob("*") if item.is_file() and not item.is_symlink()]

    def _should_exclude(self, path: Path, warnings: list[str]) -> bool:
        parts = {part.lower() for part in path.parts}
        if EXCLUDED_DIR_NAMES.intersection(parts) or path.suffix.lower() in EXCLUDED_SUFFIXES:
            return True
        if self.safety.is_sensitive_file(path):
            warnings.append(f"Đã bỏ qua file nhạy cảm: {path.name}")
            return True
        return False

    def _archive_name(self, file_path: Path, prefix: str) -> str:
        if file_path.is_file() and Path(prefix).suffix:
            arcname = prefix
        else:
            base = Path(prefix)
            if file_path == base:
                arcname = prefix
            elif file_path.is_relative_to(self.project_root):
                arcname = file_path.relative_to(self.project_root).as_posix()
            elif file_path.is_relative_to(self.app_data_root):
                arcname = f"app_data/{file_path.relative_to(self.app_data_root).as_posix()}"
            else:
                raise ValueError(f"Không backup file ngoài project/app data: {file_path}")
        return arcname.replace("\\", "/")

    def _arc_prefix_for(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        if resolved.is_relative_to(self.project_root):
            return resolved.relative_to(self.project_root).as_posix()
        if resolved.is_relative_to(self.app_data_root):
            return f"app_data/{resolved.relative_to(self.app_data_root).as_posix()}"
        return path.name

    def _relative_arcname(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        if resolved.is_relative_to(self.project_root):
            return resolved.relative_to(self.project_root).as_posix()
        if resolved.is_relative_to(self.app_data_root):
            return f"app_data/{resolved.relative_to(self.app_data_root).as_posix()}"
        return resolved.name

    def _find_export_pack_dirs(self) -> list[Path]:
        roots = [self.project_root / "outputs", self.project_root / "examples" / "outputs"]
        dirs: list[Path] = []
        for root in roots:
            if root.exists():
                dirs.extend([path for path in root.rglob("export_pack") if path.is_dir()])
        return dirs

    def _find_subtitle_files(self) -> list[Path]:
        roots = [self.project_root / "outputs", self.project_root / "examples" / "outputs"]
        files: list[Path] = []
        for root in roots:
            if root.exists():
                files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".srt", ".ass", ".vtt"})
        return files

    def _backup_dir(self, backup_folder: str | None) -> Path:
        if backup_folder:
            return Path(backup_folder).expanduser().resolve()
        return self.project_root / "backups"


def _safe_backup_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._-")[:80]


def _parse_categories(values: list[str]) -> list[DataCategory]:
    categories: list[DataCategory] = []
    for value in values:
        try:
            categories.append(DataCategory(value))
        except ValueError:
            continue
    return categories


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
