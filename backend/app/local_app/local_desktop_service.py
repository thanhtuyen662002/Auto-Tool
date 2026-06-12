from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.local_app.local_config_service import LocalConfigService
from app.local_app.local_paths_service import LocalPathsService


class LocalDesktopService:
    def __init__(
        self,
        config_service: LocalConfigService | None = None,
        paths_service: LocalPathsService | None = None,
    ) -> None:
        self.config_service = config_service or LocalConfigService()
        self.paths_service = paths_service or LocalPathsService(self.config_service)

    def open_folder(self, value: str) -> Path:
        self._ensure_enabled()
        path = self.paths_service.resolve_path(value)
        if not path.exists():
            raise FileNotFoundError(f"Folder does not exist: {path}")
        target = path if path.is_dir() else path.parent
        self._open(target)
        return target

    def reveal_file(self, value: str) -> Path:
        self._ensure_enabled()
        path = self.paths_service.resolve_path(value)
        if not path.exists():
            raise FileNotFoundError(f"File does not exist: {path}")
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            self._open(path.parent if path.is_file() else path)
        return path

    def _ensure_enabled(self) -> None:
        if not self.config_service.load_config().enable_open_folder:
            raise PermissionError("Open folder actions are disabled in Local App settings.")

    @staticmethod
    def _open(path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
