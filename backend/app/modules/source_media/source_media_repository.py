from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.utils.app_paths import app_data_dir

from .source_media_schema import SourceFolderScanResult


class SourceMediaRepository:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = (storage_root or app_data_dir() / "data").resolve()
        self.scan_root = self.storage_root / "source_media_scans"
        self.selection_root = self.storage_root / "source_media_selections"
        self.thumbnail_root = self.storage_root / "cache" / "source_thumbnails"
        self.scan_root.mkdir(parents=True, exist_ok=True)
        self.selection_root.mkdir(parents=True, exist_ok=True)
        self.thumbnail_root.mkdir(parents=True, exist_ok=True)

    def save_scan_result(self, result: SourceFolderScanResult) -> SourceFolderScanResult:
        _atomic_write_json(self.scan_path(result.folder_id), result.model_dump(mode="json"))
        return result

    def load_scan_result(self, folder_id: str) -> SourceFolderScanResult | None:
        path = self.scan_path(folder_id)
        if not path.exists():
            return None
        try:
            return SourceFolderScanResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, ValidationError):
            self._quarantine(path)
            return None

    def scan_path(self, folder_id: str) -> Path:
        return self.scan_root / f"{_safe_name(folder_id)}.json"

    def selection_path(self, selection_id: str) -> Path:
        return self.selection_root / f"{_safe_name(selection_id)}.json"

    def thumbnail_folder(self, folder_id: str) -> Path:
        path = self.thumbnail_root / _safe_name(folder_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _quarantine(self, path: Path) -> None:
        if not path.exists():
            return
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.move(str(path), str(path.with_suffix(path.suffix + f".corrupt.{suffix}")))
        except OSError:
            return


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)[:160] or "source"
