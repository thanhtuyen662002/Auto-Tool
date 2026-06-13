from __future__ import annotations

import hashlib
from pathlib import Path

from .source_media_metadata_service import SourceMediaMetadataService
from .source_media_repository import SourceMediaRepository
from .source_media_schema import (
    SourceFolderScanRequest,
    SourceFolderScanResult,
    SourceMediaOrientation,
    SourceMediaQualityFlag,
    SourceMediaStatus,
)
from .source_media_thumbnail_service import SourceMediaThumbnailService


class SourceMediaScanner:
    def __init__(
        self,
        metadata_service: SourceMediaMetadataService | None = None,
        thumbnail_service: SourceMediaThumbnailService | None = None,
        repository: SourceMediaRepository | None = None,
    ) -> None:
        self.metadata = metadata_service or SourceMediaMetadataService()
        self.thumbnails = thumbnail_service or SourceMediaThumbnailService()
        self.repository = repository or SourceMediaRepository()

    def scan_folder(self, request: SourceFolderScanRequest) -> SourceFolderScanResult:
        folder = Path(request.folder_path).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Không tìm thấy folder này: {folder}")
        folder_id = self.build_folder_id(str(folder))
        files = self.find_media_files(str(folder), request.include_extensions, request.recursive, request.max_files)
        warnings: list[str] = []
        items = []
        seen_names: set[str] = set()
        thumbnail_dir = self.repository.thumbnail_folder(folder_id)

        for file_path in files:
            item = self.metadata.probe_video(file_path).model_copy(update={"folder_id": folder_id})
            if item.filename.lower() in seen_names:
                flags = list(item.quality_flags)
                if SourceMediaQualityFlag.duplicate_name not in flags:
                    flags.append(SourceMediaQualityFlag.duplicate_name)
                item = item.model_copy(update={"quality_flags": flags, "warnings": [*item.warnings, "Tên file bị trùng."]})
            seen_names.add(item.filename.lower())
            if request.min_duration_seconds is not None and item.duration_seconds is not None and item.duration_seconds < request.min_duration_seconds:
                item = item.model_copy(update={"selected": False, "excluded_reason": "Ngắn hơn giới hạn đã chọn."})
            if request.max_duration_seconds is not None and item.duration_seconds is not None and item.duration_seconds > request.max_duration_seconds:
                item = item.model_copy(update={"selected": False, "excluded_reason": "Dài hơn giới hạn đã chọn."})
            if request.generate_thumbnails and item.status != SourceMediaStatus.unreadable:
                thumbnail = self.thumbnails.generate_thumbnail(
                    item.path,
                    str(thumbnail_dir),
                    request.thumbnail_at_second,
                    item.id,
                )
                if thumbnail:
                    item = item.model_copy(update={"thumbnail_path": thumbnail})
                else:
                    item = item.model_copy(update={"warnings": [*item.warnings, "Không tạo được thumbnail."]})
                    warnings.append(f"Không tạo được thumbnail cho {item.filename}.")
            items.append(item)

        result = SourceFolderScanResult(
            success=True,
            folder_path=str(folder),
            folder_id=folder_id,
            total_files_found=len(files),
            valid_videos=sum(1 for item in items if item.status == SourceMediaStatus.valid),
            warning_videos=sum(1 for item in items if item.status == SourceMediaStatus.warning),
            unreadable_files=sum(1 for item in items if item.status in {SourceMediaStatus.unreadable, SourceMediaStatus.missing}),
            vertical_count=sum(1 for item in items if item.orientation == SourceMediaOrientation.vertical),
            horizontal_count=sum(1 for item in items if item.orientation == SourceMediaOrientation.horizontal),
            square_count=sum(1 for item in items if item.orientation == SourceMediaOrientation.square),
            selected_count=sum(1 for item in items if item.selected),
            items=items,
            warnings=_dedupe(warnings),
            errors=[],
        )
        self.repository.save_scan_result(result)
        return result

    def find_media_files(
        self,
        folder_path: str,
        extensions: list[str],
        recursive: bool,
        max_files: int | None,
    ) -> list[str]:
        folder = Path(folder_path).expanduser().resolve()
        allowed = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
        iterator = folder.rglob("*") if recursive else folder.iterdir()
        files = [
            path.resolve()
            for path in iterator
            if path.is_file() and path.suffix.lower() in allowed and _is_inside(path.resolve(), folder)
        ]
        files = sorted(files, key=lambda path: path.name.lower())
        if max_files is not None:
            files = files[:max_files]
        return [str(path) for path in files]

    def build_folder_id(self, folder_path: str) -> str:
        resolved = str(Path(folder_path).expanduser().resolve()).lower()
        return "folder_" + hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]


def _is_inside(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result
