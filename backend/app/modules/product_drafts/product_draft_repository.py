from __future__ import annotations

import json
from typing import Any

from app import database
from app.modules.product_drafts.product_draft_schema import ProductDraft, ProductDraftSource, ProductDraftStatus
from app.modules.product_import.product_import_schema import ProductInfoNormalized, ProductValidationIssue


class ProductDraftRepository:
    def create(self, draft: ProductDraft) -> ProductDraft:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO product_drafts (
                    id, title, status, source_name, source_url, imported_by, imported_at,
                    raw_input_json, raw_text, structured_data_json, extractor_debug_json,
                    normalized_product_json, validation_issues_json,
                    industry_preset_id, confidence_score, user_note, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _draft_values(draft),
            )
        saved = self.get(draft.id)
        assert saved is not None
        return saved

    def list(
        self,
        *,
        status: str | None = None,
        source_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ProductDraft], int]:
        database.init_db()
        where, values = _filter_clause(status=status, source_name=source_name)
        limit_value = max(1, min(int(limit), 200))
        offset_value = max(0, int(offset))
        with database.get_connection() as conn:
            total_row = conn.execute(f"SELECT COUNT(*) AS total FROM product_drafts {where}", values).fetchone()
            rows = conn.execute(
                f"""
                SELECT *
                FROM product_drafts
                {where}
                ORDER BY created_at DESC, updated_at DESC
                LIMIT ? OFFSET ?
                """,
                [*values, limit_value, offset_value],
            ).fetchall()
        total = int(total_row["total"] if total_row else 0)
        return [_row_to_draft(row) for row in rows], total

    def get(self, draft_id: str) -> ProductDraft | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM product_drafts WHERE id = ?", (draft_id,)).fetchone()
        return _row_to_draft(row) if row else None

    def update(self, draft_id: str, updates: dict[str, Any]) -> ProductDraft | None:
        database.init_db()
        fields = {key: value for key, value in updates.items() if key in _UPDATABLE_COLUMNS}
        if not fields:
            return self.get(draft_id)

        fields["updated_at"] = updates.get("updated_at") or _now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = [_encode_column_value(key, value) for key, value in fields.items()]
        values.append(draft_id)
        with database.get_connection() as conn:
            conn.execute(f"UPDATE product_drafts SET {assignments} WHERE id = ?", values)
        return self.get(draft_id)

    def delete(self, draft_id: str) -> bool:
        database.init_db()
        with database.get_connection() as conn:
            cursor = conn.execute("DELETE FROM product_drafts WHERE id = ?", (draft_id,))
        return cursor.rowcount > 0

    def clear_archived(self) -> int:
        database.init_db()
        with database.get_connection() as conn:
            cursor = conn.execute("DELETE FROM product_drafts WHERE status = ?", (ProductDraftStatus.archived.value,))
        return int(cursor.rowcount)


_UPDATABLE_COLUMNS = {
    "title",
    "status",
    "normalized_product_json",
    "validation_issues_json",
    "extractor_debug_json",
    "industry_preset_id",
    "confidence_score",
    "user_note",
    "updated_at",
}


def _draft_values(draft: ProductDraft) -> tuple[Any, ...]:
    return (
        draft.id,
        draft.title,
        draft.status.value,
        draft.source.source_name,
        draft.source.source_url,
        draft.source.imported_by,
        draft.source.imported_at,
        _json_dumps(draft.raw_input),
        draft.raw_text,
        _json_dumps(draft.structured_data),
        _json_dumps(draft.extractor_debug),
        _model_json(draft.normalized_product),
        _json_dumps([issue.model_dump(mode="json") for issue in draft.validation_issues]),
        draft.industry_preset_id,
        draft.confidence_score,
        draft.user_note,
        draft.created_at,
        draft.updated_at,
    )


def _filter_clause(*, status: str | None, source_name: str | None) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if status:
        clauses.append("status = ?")
        values.append(status)
    if source_name:
        clauses.append("source_name = ?")
        values.append(source_name)
    if not clauses:
        return "", values
    return f"WHERE {' AND '.join(clauses)}", values


def _row_to_draft(row: Any) -> ProductDraft:
    data = dict(row)
    normalized_product = _loads_optional(data.get("normalized_product_json"))
    issues = _loads_optional(data.get("validation_issues_json")) or []
    return ProductDraft(
        id=data["id"],
        title=data["title"],
        status=ProductDraftStatus(data["status"]),
        source=ProductDraftSource(
            source_name=data.get("source_name"),
            source_url=data.get("source_url"),
            imported_by=data.get("imported_by") or "chrome_extension",
            imported_at=data.get("imported_at") or data["created_at"],
        ),
        raw_input=_loads_optional(data.get("raw_input_json")),
        raw_text=data.get("raw_text"),
        structured_data=_loads_optional(data.get("structured_data_json")),
        extractor_debug=_loads_optional(data.get("extractor_debug_json")),
        normalized_product=ProductInfoNormalized.model_validate(normalized_product) if normalized_product else None,
        validation_issues=[ProductValidationIssue.model_validate(issue) for issue in issues],
        industry_preset_id=data.get("industry_preset_id"),
        confidence_score=float(data.get("confidence_score") or 0.0),
        user_note=data.get("user_note"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


def _encode_column_value(key: str, value: Any) -> Any:
    if key in {"normalized_product_json", "validation_issues_json", "extractor_debug_json"}:
        return _json_dumps(value)
    return value


def _model_json(value: Any) -> str | None:
    if value is None:
        return None
    return _json_dumps(value.model_dump(mode="json"))


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _loads_optional(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
