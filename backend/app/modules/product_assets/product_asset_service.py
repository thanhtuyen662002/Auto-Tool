from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app import database
from app.modules.product_assets.product_asset_downloader import ProductAssetDownloader, copy_local_image
from app.modules.product_assets.product_asset_repository import ProductAssetRepository
from app.modules.product_assets.product_asset_schema import (
    ImportAssetsFromDraftRequest,
    ProductAsset,
    ProductAssetRole,
    ProductAssetStatus,
    ProductAssetType,
    UpdateProductAssetRequest,
)
from app.modules.product_drafts.product_draft_repository import ProductDraftRepository
from app.modules.product_drafts.product_draft_schema import ProductDraft
from app.schemas.project_schema import ProjectAssetSettings, ProjectConfig
from app.utils.app_paths import app_data_dir
from app.utils.file_utils import ensure_dir, write_json


class ProductAssetService:
    def __init__(
        self,
        repository: ProductAssetRepository | None = None,
        draft_repository: ProductDraftRepository | None = None,
        downloader: ProductAssetDownloader | None = None,
    ) -> None:
        self.repository = repository or ProductAssetRepository()
        self.draft_repository = draft_repository or ProductDraftRepository()
        self.downloader = downloader or ProductAssetDownloader()

    def list_assets_for_draft(self, draft_id: str) -> list[ProductAsset]:
        draft = self._get_draft(draft_id)
        self._ensure_pending_assets_from_draft(draft)
        return self.repository.list_for_draft(draft_id)

    def list_assets_for_project(self, project_id: str) -> list[ProductAsset]:
        if not database.get_project(project_id):
            raise LookupError(f"Project not found: {project_id}")
        return self.repository.list_for_project(project_id)

    def import_assets_from_draft(self, request: ImportAssetsFromDraftRequest) -> list[ProductAsset]:
        draft_id = request.draft_id
        if not draft_id:
            raise ValueError("draft_id is required.")
        draft = self._get_draft(draft_id)
        self._ensure_pending_assets_from_draft(draft)
        assets = self.repository.list_for_draft(draft_id)
        selected_urls = set(request.selected_asset_urls) if request.selected_asset_urls is not None else {
            asset.original_url for asset in assets if asset.original_url
        }
        output_dir = self._output_dir_for_import(draft_id, request.project_id)
        imported: list[ProductAsset] = []
        for index, asset in enumerate(assets, start=1):
            selected = bool(asset.original_url and asset.original_url in selected_urls)
            if not selected:
                imported.append(asset)
                continue
            role = asset.role
            if role == ProductAssetRole.reference and not any(item.role == ProductAssetRole.main_product for item in imported):
                role = ProductAssetRole.main_product
            updated = self.repository.update(asset.id, {"is_selected": True, "role": role})
            asset = updated or asset
            if request.project_id:
                asset = self._attach_one_asset(asset, request.project_id, output_dir, index)
            elif request.download_selected:
                asset = self._download_or_mark(asset, output_dir, index)
            imported.append(asset)

        if request.project_id:
            self._sync_project_config_assets(request.project_id)
        self._write_import_log(draft_id, request.project_id, output_dir, imported)
        return imported

    def update_asset(self, asset_id: str, request: UpdateProductAssetRequest) -> ProductAsset:
        asset = self.repository.get(asset_id)
        if not asset:
            raise LookupError(f"Product asset not found: {asset_id}")
        updates: dict[str, Any] = {}
        if request.role is not None:
            updates["role"] = request.role.value
        if request.is_selected is not None:
            updates["is_selected"] = request.is_selected
        if request.user_note is not None:
            updates["user_note"] = request.user_note
        updated = self.repository.update(asset_id, updates)
        if not updated:
            raise LookupError(f"Product asset not found: {asset_id}")
        if updated.project_id:
            self._sync_project_config_assets(updated.project_id)
        return updated

    def delete_asset(self, asset_id: str) -> ProductAsset:
        asset = self.repository.get(asset_id)
        if not asset:
            raise LookupError(f"Product asset not found: {asset_id}")
        updated = self.repository.mark_skipped(asset_id)
        if not updated:
            raise LookupError(f"Product asset not found: {asset_id}")
        if updated.project_id:
            self._sync_project_config_assets(updated.project_id)
        return updated

    def attach_draft_assets_to_project(
        self,
        draft_id: str,
        project_id: str,
        selected_asset_ids: list[str] | None = None,
    ) -> list[ProductAsset]:
        draft = self._get_draft(draft_id)
        if not database.get_project(project_id):
            raise LookupError(f"Project not found: {project_id}")
        self._ensure_pending_assets_from_draft(draft)
        assets = self.repository.list_for_draft(draft_id)
        selected_ids = set(selected_asset_ids or [])
        if selected_ids:
            assets = [asset for asset in assets if asset.id in selected_ids]
        else:
            selected_assets = [asset for asset in assets if asset.is_selected]
            assets = selected_assets or assets

        output_dir = self._output_dir_for_import(draft_id, project_id)
        attached: list[ProductAsset] = []
        for index, asset in enumerate(assets, start=1):
            attached.append(self._attach_one_asset(asset, project_id, output_dir, index))

        self._sync_project_config_assets(project_id)
        self._write_import_log(draft_id, project_id, output_dir, attached)
        return attached

    def _attach_one_asset(self, asset: ProductAsset, project_id: str, output_dir: Path, index: int) -> ProductAsset:
        updates = {
            "project_id": project_id,
            "is_selected": True,
            "role": asset.role.value,
        }
        updated = self.repository.update(asset.id, updates) or asset
        if updated.asset_type != ProductAssetType.image:
            return self.repository.update(
                updated.id,
                {
                    "status": ProductAssetStatus.skipped.value,
                    "warnings": [*updated.warnings, "Video assets are stored as metadata only in this version."],
                },
            ) or updated
        if updated.local_path and Path(updated.local_path).exists():
            copied = copy_local_image(updated.local_path, str(output_dir), f"product_asset_{index:03d}")
        else:
            copied = self._download_or_mark(updated, output_dir, index)
            if copied.id == updated.id:
                return copied
        return self.repository.update(
            updated.id,
            {
                "project_id": project_id,
                "status": copied.status.value,
                "filename": copied.filename,
                "local_path": copied.local_path,
                "width": copied.width,
                "height": copied.height,
                "file_size": copied.file_size,
                "mime_type": copied.mime_type,
                "quality_score": copied.quality_score,
                "warnings": copied.warnings,
                "errors": copied.errors,
            },
        ) or updated

    def _download_or_mark(self, asset: ProductAsset, output_dir: Path, index: int) -> ProductAsset:
        if asset.asset_type != ProductAssetType.image or not asset.original_url:
            return self.repository.update(
                asset.id,
                {
                    "status": ProductAssetStatus.skipped.value,
                    "warnings": [*asset.warnings, "Only image assets are downloaded in this version."],
                },
            ) or asset
        downloaded = self.downloader.download_image(asset.original_url, str(output_dir), f"product_asset_{index:03d}")
        return self.repository.update(
            asset.id,
            {
                "status": downloaded.status.value,
                "filename": downloaded.filename,
                "local_path": downloaded.local_path,
                "width": downloaded.width,
                "height": downloaded.height,
                "file_size": downloaded.file_size,
                "mime_type": downloaded.mime_type,
                "quality_score": downloaded.quality_score,
                "warnings": downloaded.warnings,
                "errors": downloaded.errors,
                "is_selected": True,
            },
        ) or asset

    def _ensure_pending_assets_from_draft(self, draft: ProductDraft) -> list[ProductAsset]:
        existing = {asset.original_url: asset for asset in self.repository.list_for_draft(draft.id)}
        urls = extract_image_urls_from_draft(draft)
        created: list[ProductAsset] = []
        now = _now()
        for index, url in enumerate(urls, start=1):
            if url in existing:
                created.append(existing[url])
                continue
            role = ProductAssetRole.main_product if index == 1 else ProductAssetRole.reference
            asset = ProductAsset(
                id=asset_id_for_url(draft.id, url),
                draft_id=draft.id,
                source_name=draft.source.source_name,
                source_url=draft.source.source_url,
                original_url=url,
                asset_type=ProductAssetType.image,
                role=role,
                status=ProductAssetStatus.pending,
                created_at=now,
                updated_at=now,
            )
            created.append(self.repository.upsert(asset))
        return created

    def _get_draft(self, draft_id: str) -> ProductDraft:
        draft = self.draft_repository.get(draft_id)
        if not draft:
            raise LookupError(f"Product draft not found: {draft_id}")
        return draft

    def _output_dir_for_import(self, draft_id: str, project_id: str | None) -> Path:
        if project_id:
            project = database.get_project(project_id)
            if not project:
                raise LookupError(f"Project not found: {project_id}")
            config = ProjectConfig.model_validate(project["config"])
            return ensure_dir(Path(config.output_folder) / config.project_name / "assets" / "product")
        return ensure_dir(app_data_dir() / "data" / "imported_assets" / "drafts" / draft_id)

    def _sync_project_config_assets(self, project_id: str) -> None:
        project = database.get_project(project_id)
        if not project:
            return
        config = ProjectConfig.model_validate(project["config"])
        assets = [
            asset
            for asset in self.repository.list_for_project(project_id)
            if asset.status == ProductAssetStatus.downloaded and asset.is_selected
        ]
        main = next((asset for asset in assets if asset.role == ProductAssetRole.main_product), None)
        reference_ids = [asset.id for asset in assets if asset.role == ProductAssetRole.reference]
        poster_ids = [asset.id for asset in assets if asset.role == ProductAssetRole.poster]
        updated_config = config.model_copy(
            update={
                "assets": ProjectAssetSettings(
                    main_product_asset_id=main.id if main else None,
                    reference_asset_ids=reference_ids,
                    poster_asset_ids=poster_ids,
                )
            }
        )
        database.update_project_config(project_id, updated_config.model_dump(mode="json"))

    def _write_import_log(
        self,
        draft_id: str,
        project_id: str | None,
        output_dir: Path,
        items: list[ProductAsset],
    ) -> None:
        log = {
            "draft_id": draft_id,
            "project_id": project_id,
            "total_urls": len([item for item in items if item.original_url]),
            "downloaded": sum(1 for item in items if item.status == ProductAssetStatus.downloaded),
            "failed": sum(1 for item in items if item.status == ProductAssetStatus.failed),
            "skipped": sum(1 for item in items if item.status == ProductAssetStatus.skipped),
            "items": [
                {
                    "url": item.original_url,
                    "status": item.status.value,
                    "local_path": item.local_path,
                    "width": item.width,
                    "height": item.height,
                    "quality_score": item.quality_score,
                    "warnings": item.warnings,
                    "errors": item.errors,
                }
                for item in items
            ],
        }
        write_json(output_dir / "product_assets_import_log.json", log)


def extract_image_urls_from_draft(draft: ProductDraft) -> list[str]:
    candidates: list[str] = []
    payloads = [draft.structured_data, draft.raw_input]
    for payload in payloads:
        if isinstance(payload, dict):
            candidates.extend(_urls_at_path(payload, ["images"]))
            candidates.extend(_urls_at_path(payload, ["structured_data", "images"]))
            candidates.extend(_urls_at_path(payload, ["shopee", "images"]))
            candidates.extend(_urls_at_path(payload, ["structured_data", "shopee", "images"]))
    return _dedupe_urls(candidates)


def asset_id_for_url(draft_id: str, url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"auto-tool-product-asset:{draft_id}:{url}"))


def _urls_at_path(payload: dict[str, Any], path: list[str]) -> list[str]:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return []
        current = current.get(key)
    if not isinstance(current, list):
        return []
    return [item for item in current if isinstance(item, str) and _is_supported_url(item)]


def _is_supported_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"}


def _dedupe_urls(values: list[str]) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        url = value.strip()
        if not url or url in seen:
            continue
        results.append(url)
        seen.add(url)
    return results


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
