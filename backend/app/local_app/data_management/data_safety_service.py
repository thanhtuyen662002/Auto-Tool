from __future__ import annotations

import os
from pathlib import Path

from app.local_app.data_management.data_management_schema import CleanupTarget


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SENSITIVE_EXACT_NAMES = {".env", "credentials.json", "token.json"}
SENSITIVE_SUFFIXES = {".key", ".pem"}


class DataSafetyService:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()

    def is_path_inside_project(self, path: str | Path) -> bool:
        try:
            Path(path).expanduser().resolve().relative_to(self.project_root)
            return True
        except (OSError, ValueError):
            return False

    def is_safe_to_delete(self, path: str | Path, target: CleanupTarget) -> tuple[bool, str]:
        resolved = Path(path).expanduser().resolve()
        if not self.is_path_inside_project(resolved):
            return False, "Đường dẫn nằm ngoài project root."

        rel_parts = {part.lower() for part in resolved.relative_to(self.project_root).parts}
        if "config" in rel_parts:
            return False, "Không xóa thư mục config bằng cleanup."
        if "data" in rel_parts and resolved.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            return False, "Không xóa database bằng cleanup."
        if self.is_sensitive_file(resolved):
            return False, "Không xóa file nhạy cảm bằng cleanup."

        if target == CleanupTarget.failed_partial_renders and resolved.suffix.lower() in VIDEO_SUFFIXES:
            return False, "Không xóa video final/nguồn theo target failed_partial_renders."
        return True, "OK"

    def is_sensitive_file(self, path: str | Path) -> bool:
        target = Path(path)
        name = target.name.lower()
        if name in SENSITIVE_EXACT_NAMES or name.startswith(".env."):
            return True
        if target.suffix.lower() in SENSITIVE_SUFFIXES:
            return True
        return False

    def prevent_zip_slip(self, zip_member_name: str) -> bool:
        normalized = zip_member_name.replace("\\", "/")
        if not normalized or normalized.startswith("/") or normalized.startswith("../"):
            return False
        if os.path.isabs(normalized):
            return False
        parts = [part for part in normalized.split("/") if part]
        if any(part == ".." for part in parts):
            return False
        if parts and ":" in parts[0]:
            return False
        return True

