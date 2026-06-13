from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from app.local_app.data_management.data_management_schema import (
    CleanupPreviewItem,
    CleanupRequest,
    CleanupResult,
    CleanupTarget,
)
from app.local_app.data_management.data_safety_service import DataSafetyService


class CleanupService:
    def __init__(self, project_root: Path | None = None, safety: DataSafetyService | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.safety = safety or DataSafetyService(self.project_root)

    def preview_cleanup(self, request: CleanupRequest) -> CleanupResult:
        return self._build_result(request.model_copy(update={"dry_run": True, "confirm_delete": False}))

    def run_cleanup(self, request: CleanupRequest) -> CleanupResult:
        if request.dry_run or not request.confirm_delete:
            result = self._build_result(request.model_copy(update={"dry_run": True}))
            result.warnings.append("Cleanup chưa xóa file vì dry_run=true hoặc confirm_delete=false.")
            return result
        return self._build_result(request)

    def _build_result(self, request: CleanupRequest) -> CleanupResult:
        warnings: list[str] = []
        errors: list[str] = []
        preview_items = self._collect_preview_items(request, warnings)
        deleted_size = 0
        deleted_count = 0
        if not request.dry_run and request.confirm_delete:
            for item in preview_items:
                path = Path(item.path)
                safe, reason = self.safety.is_safe_to_delete(path, item.target)
                if not safe:
                    warnings.append(f"Bỏ qua {path}: {reason}")
                    continue
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    elif path.exists():
                        path.unlink()
                    deleted_size += item.size_bytes
                    deleted_count += item.file_count
                except OSError as exc:
                    errors.append(f"Không thể xóa {path}: {exc}")
        return CleanupResult(
            success=not errors,
            dry_run=request.dry_run or not request.confirm_delete,
            deleted_size_bytes=deleted_size,
            deleted_file_count=deleted_count,
            preview_items=preview_items,
            warnings=warnings,
            errors=errors,
        )

    def _collect_preview_items(self, request: CleanupRequest, warnings: list[str]) -> list[CleanupPreviewItem]:
        cutoff = datetime.now() - timedelta(days=max(0, request.older_than_days))
        items: list[CleanupPreviewItem] = []
        for target in request.targets:
            for path, reason in self._target_candidates(target):
                if not path.exists():
                    continue
                if target not in {CleanupTarget.temp_files, CleanupTarget.cache_files} and not _older_than(path, cutoff):
                    continue
                safe, safety_reason = self.safety.is_safe_to_delete(path, target)
                if not safe:
                    warnings.append(f"Bỏ qua {path}: {safety_reason}")
                    continue
                size, file_count = _path_size(path)
                if file_count <= 0:
                    continue
                items.append(
                    CleanupPreviewItem(
                        path=str(path),
                        target=target,
                        size_bytes=size,
                        file_count=file_count,
                        reason=reason,
                    )
                )
        return _dedupe_items(items)

    def _target_candidates(self, target: CleanupTarget) -> list[tuple[Path, str]]:
        if target == CleanupTarget.launcher_logs:
            return [(path, f"Launcher log cũ hơn ngưỡng ngày đã chọn") for path in (self.project_root / "logs" / "launcher").glob("*.log")]
        if target == CleanupTarget.debug_logs:
            logs = self.project_root / "logs"
            return [(path, "Debug log cũ hơn ngưỡng ngày đã chọn") for path in logs.rglob("*debug*.log")] if logs.exists() else []
        if target == CleanupTarget.temp_files:
            return [(self.project_root / "temp", "Thư mục temp local")]
        if target == CleanupTarget.cache_files:
            return [(self.project_root / "cache", "Thư mục cache local")]
        if target == CleanupTarget.preview_frames:
            return [(path, "Preview/generated frames") for root in _output_roots(self.project_root) for path in _frame_dirs(root)]
        if target == CleanupTarget.failed_partial_renders:
            return [
                (path, "File render tạm/partial/failed không phải video final")
                for root in _output_roots(self.project_root)
                for path in root.rglob("*")
                if path.exists()
                and ("partial" in path.name.lower() or "failed" in path.name.lower())
                and path.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi"}
            ]
        if target == CleanupTarget.old_exports:
            return [(path, "Export pack cũ hơn ngưỡng ngày đã chọn") for root in _output_roots(self.project_root) for path in root.rglob("export_pack") if path.is_dir()]
        return []


def _output_roots(project_root: Path) -> list[Path]:
    return [path for path in [project_root / "outputs", project_root / "examples" / "outputs"] if path.exists()]


def _frame_dirs(root: Path) -> list[Path]:
    result: list[Path] = []
    for name in ("frames", "preview_frames"):
        result.extend(path for path in root.rglob(name) if path.is_dir())
    return result


def _older_than(path: Path, cutoff: datetime) -> bool:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime) < cutoff
    except OSError:
        return False


def _path_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    if path.is_file():
        return path.stat().st_size, 1
    total = 0
    count = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
                count += 1
        except OSError:
            continue
    return total, count


def _dedupe_items(items: list[CleanupPreviewItem]) -> list[CleanupPreviewItem]:
    deduped: dict[str, CleanupPreviewItem] = {}
    for item in items:
        deduped[item.path] = item
    return list(deduped.values())

