from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .source_media_repository import SourceMediaRepository, _atomic_write_json
from .source_media_schema import SourceMediaSelectionRequest, SourceMediaSelectionResult, SourceMediaStatus


class SourceMediaSelectionService:
    def __init__(self, repository: SourceMediaRepository | None = None) -> None:
        self.repository = repository or SourceMediaRepository()

    def create_selection(self, request: SourceMediaSelectionRequest) -> SourceMediaSelectionResult:
        scan = self.repository.load_scan_result(request.folder_id)
        if scan is None:
            return SourceMediaSelectionResult(
                success=False,
                folder_id=request.folder_id,
                errors=[f"Không tìm thấy scan result cho folder_id: {request.folder_id}"],
            )
        items_by_id = {item.id: item for item in scan.items}
        selected_ids = [item_id for item_id in request.selected_item_ids if item_id not in set(request.excluded_item_ids)]
        selected_paths: list[str] = []
        warnings: list[str] = []
        for item_id in selected_ids:
            item = items_by_id.get(item_id)
            if not item:
                warnings.append(f"Item không tồn tại trong scan: {item_id}")
                continue
            if item.status in {SourceMediaStatus.unreadable, SourceMediaStatus.unsupported, SourceMediaStatus.missing}:
                warnings.append(f"Bỏ qua file không dùng được: {item.filename}")
                continue
            selected_paths.append(item.path)
        selection_id = "sel_" + uuid.uuid4().hex[:16]
        payload = {
            "selection_id": selection_id,
            "folder_id": request.folder_id,
            "folder_path": scan.folder_path,
            "selection_name": request.selection_name,
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
            "selected_item_ids": selected_ids,
            "selected_paths": selected_paths,
            "excluded_item_ids": request.excluded_item_ids,
            "priorities": request.priorities,
        }
        _atomic_write_json(self.repository.selection_path(selection_id), payload)
        return SourceMediaSelectionResult(
            success=True,
            folder_id=request.folder_id,
            selection_id=selection_id,
            selected_count=len(selected_paths),
            excluded_count=len(request.excluded_item_ids),
            selected_paths=selected_paths,
            warnings=warnings,
            errors=[],
        )

    def get_selection(self, selection_id: str) -> SourceMediaSelectionResult:
        payload = self._load_selection_payload(selection_id)
        if payload is None:
            return SourceMediaSelectionResult(success=False, folder_id="", selection_id=selection_id, errors=["Không tìm thấy selection."])
        return SourceMediaSelectionResult(
            success=True,
            folder_id=str(payload.get("folder_id") or ""),
            selection_id=selection_id,
            selected_count=len(payload.get("selected_paths") or []),
            excluded_count=len(payload.get("excluded_item_ids") or []),
            selected_paths=list(payload.get("selected_paths") or []),
            warnings=[],
            errors=[],
        )

    def get_selected_paths(self, selection_id: str) -> list[str]:
        result = self.get_selection(selection_id)
        return result.selected_paths if result.success else []

    def get_priorities(self, selection_id: str) -> dict[str, str]:
        payload = self._load_selection_payload(selection_id) or {}
        return dict(payload.get("priorities") or {})

    def get_priority_by_path(self, selection_id: str) -> dict[str, str]:
        payload = self._load_selection_payload(selection_id) or {}
        folder_id = str(payload.get("folder_id") or "")
        scan = self.repository.load_scan_result(folder_id) if folder_id else None
        if scan is None:
            return {}
        priorities = dict(payload.get("priorities") or {})
        selected_ids = list(payload.get("selected_item_ids") or [])
        by_id = {item.id: item for item in scan.items}
        result: dict[str, str] = {}
        for item_id in selected_ids:
            item = by_id.get(item_id)
            priority = priorities.get(item_id)
            if item is None or priority not in {"low", "normal", "high"}:
                continue
            result[str(Path(item.path).expanduser().resolve()).lower()] = priority
        return result

    def _load_selection_payload(self, selection_id: str) -> dict[str, Any] | None:
        path = self.repository.selection_path(selection_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            try:
                path.rename(path.with_suffix(path.suffix + ".corrupt"))
            except OSError:
                pass
            return None
