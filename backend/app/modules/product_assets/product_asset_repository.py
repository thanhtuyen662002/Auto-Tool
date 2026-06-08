from __future__ import annotations

import json
from typing import Any

from app import database
from app.modules.product_assets.product_asset_schema import (
    ProductAsset,
    ProductAssetRole,
    ProductAssetStatus,
    ProductAssetType,
)


class ProductAssetRepository:
    def upsert(self, asset: ProductAsset) -> ProductAsset:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO product_assets (
                    id, project_id, draft_id, source_name, source_url, original_url,
                    asset_type, role, status, filename, local_path, width, height,
                    file_size, mime_type, quality_score, is_selected, user_note,
                    warnings_json, errors_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id = excluded.project_id,
                    draft_id = excluded.draft_id,
                    source_name = excluded.source_name,
                    source_url = excluded.source_url,
                    original_url = excluded.original_url,
                    asset_type = excluded.asset_type,
                    role = excluded.role,
                    status = excluded.status,
                    filename = excluded.filename,
                    local_path = excluded.local_path,
                    width = excluded.width,
                    height = excluded.height,
                    file_size = excluded.file_size,
                    mime_type = excluded.mime_type,
                    quality_score = excluded.quality_score,
                    is_selected = excluded.is_selected,
                    user_note = excluded.user_note,
                    warnings_json = excluded.warnings_json,
                    errors_json = excluded.errors_json,
                    updated_at = excluded.updated_at
                """,
                _asset_values(asset),
            )
        saved = self.get(asset.id)
        assert saved is not None
        return saved

    def get(self, asset_id: str) -> ProductAsset | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM product_assets WHERE id = ?", (asset_id,)).fetchone()
        return _row_to_asset(row) if row else None

    def list_for_draft(self, draft_id: str) -> list[ProductAsset]:
        return self._list("draft_id = ?", [draft_id])

    def list_for_project(self, project_id: str) -> list[ProductAsset]:
        return self._list("project_id = ?", [project_id])

    def list_for_draft_or_project(self, draft_id: str | None, project_id: str | None) -> list[ProductAsset]:
        clauses: list[str] = []
        values: list[Any] = []
        if draft_id:
            clauses.append("draft_id = ?")
            values.append(draft_id)
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if not clauses:
            return []
        return self._list(" OR ".join(clauses), values)

    def update(self, asset_id: str, updates: dict[str, Any]) -> ProductAsset | None:
        database.init_db()
        allowed = {
            "project_id",
            "draft_id",
            "role",
            "status",
            "filename",
            "local_path",
            "width",
            "height",
            "file_size",
            "mime_type",
            "quality_score",
            "is_selected",
            "user_note",
            "warnings",
            "errors",
            "updated_at",
        }
        fields = {key: value for key, value in updates.items() if key in allowed}
        if not fields:
            return self.get(asset_id)
        if "updated_at" not in fields:
            fields["updated_at"] = database._now()
        assignments = ", ".join(f"{_column_name(key)} = ?" for key in fields)
        values = [_encode_value(key, value) for key, value in fields.items()]
        values.append(asset_id)
        with database.get_connection() as conn:
            conn.execute(f"UPDATE product_assets SET {assignments} WHERE id = ?", values)
        return self.get(asset_id)

    def mark_skipped(self, asset_id: str) -> ProductAsset | None:
        return self.update(asset_id, {"status": ProductAssetStatus.skipped.value, "is_selected": False})

    def _list(self, where: str, values: list[Any]) -> list[ProductAsset]:
        database.init_db()
        with database.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM product_assets
                WHERE {where}
                ORDER BY
                    CASE role
                        WHEN 'main_product' THEN 0
                        WHEN 'reference' THEN 1
                        WHEN 'poster' THEN 2
                        WHEN 'thumbnail' THEN 3
                        WHEN 'description' THEN 4
                        WHEN 'variation' THEN 5
                        ELSE 6
                    END,
                    created_at ASC,
                    id ASC
                """,
                values,
            ).fetchall()
        return [_row_to_asset(row) for row in rows]


def _asset_values(asset: ProductAsset) -> tuple[Any, ...]:
    return (
        asset.id,
        asset.project_id,
        asset.draft_id,
        asset.source_name,
        asset.source_url,
        asset.original_url,
        asset.asset_type.value,
        asset.role.value,
        asset.status.value,
        asset.filename,
        asset.local_path,
        asset.width,
        asset.height,
        asset.file_size,
        asset.mime_type,
        asset.quality_score,
        int(asset.is_selected),
        asset.user_note,
        json.dumps(asset.warnings, ensure_ascii=False),
        json.dumps(asset.errors, ensure_ascii=False),
        asset.created_at,
        asset.updated_at,
    )


def _row_to_asset(row: Any) -> ProductAsset:
    data = dict(row)
    return ProductAsset(
        id=data["id"],
        project_id=data.get("project_id"),
        draft_id=data.get("draft_id"),
        source_name=data.get("source_name"),
        source_url=data.get("source_url"),
        original_url=data.get("original_url"),
        asset_type=ProductAssetType(data.get("asset_type") or ProductAssetType.unknown.value),
        role=ProductAssetRole(data.get("role") or ProductAssetRole.reference.value),
        status=ProductAssetStatus(data.get("status") or ProductAssetStatus.pending.value),
        filename=data.get("filename"),
        local_path=data.get("local_path"),
        width=data.get("width"),
        height=data.get("height"),
        file_size=data.get("file_size"),
        mime_type=data.get("mime_type"),
        quality_score=data.get("quality_score"),
        is_selected=bool(data.get("is_selected")),
        user_note=data.get("user_note"),
        warnings=_loads_list(data.get("warnings_json")),
        errors=_loads_list(data.get("errors_json")),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def _column_name(key: str) -> str:
    if key == "warnings":
        return "warnings_json"
    if key == "errors":
        return "errors_json"
    return key


def _encode_value(key: str, value: Any) -> Any:
    if key in {"warnings", "errors"}:
        return json.dumps(value or [], ensure_ascii=False)
    if key in {"role", "status"} and hasattr(value, "value"):
        return value.value
    if key == "is_selected":
        return int(bool(value))
    return value


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []
