from __future__ import annotations

import json
from typing import Any

from app import database
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import SubtitleRewriteSuggestion


class SubtitleRewriteRepository:
    def create_many(self, suggestions: list[SubtitleRewriteSuggestion]) -> list[SubtitleRewriteSuggestion]:
        if not suggestions:
            return []
        database.init_db()
        with database.get_connection() as conn:
            for suggestion in suggestions:
                conn.execute(
                    """
                    INSERT INTO subtitle_rewrite_suggestions (
                        id, document_id, line_index, source_text, original_translation,
                        suggested_text, style, reason, char_count_before, char_count_after,
                        estimated_cps_before, estimated_cps_after, safety_warnings_json,
                        quality_score_before, quality_score_after, created_at, applied_at, auto_applied
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _values(suggestion),
                )
        return suggestions

    def get(self, suggestion_id: str) -> SubtitleRewriteSuggestion | None:
        database.init_db()
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM subtitle_rewrite_suggestions WHERE id = ?",
                (suggestion_id,),
            ).fetchone()
        return _row_to_suggestion(row) if row else None

    def list_for_line(self, document_id: str, line_index: int) -> list[SubtitleRewriteSuggestion]:
        database.init_db()
        with database.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subtitle_rewrite_suggestions
                WHERE document_id = ? AND line_index = ?
                ORDER BY created_at DESC
                """,
                (document_id, line_index),
            ).fetchall()
        return [_row_to_suggestion(row) for row in rows]

    def list_for_document(self, document_id: str) -> list[SubtitleRewriteSuggestion]:
        database.init_db()
        with database.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM subtitle_rewrite_suggestions
                WHERE document_id = ?
                ORDER BY created_at DESC
                """,
                (document_id,),
            ).fetchall()
        return [_row_to_suggestion(row) for row in rows]

    def mark_applied(self, suggestion_id: str, applied_at: str, *, auto_applied: bool) -> None:
        database.init_db()
        with database.get_connection() as conn:
            conn.execute(
                """
                UPDATE subtitle_rewrite_suggestions
                SET applied_at = ?, auto_applied = ?
                WHERE id = ?
                """,
                (applied_at, int(auto_applied), suggestion_id),
            )

    def stats_for_documents(self, document_ids: list[str]) -> dict[str, float | int]:
        if not document_ids:
            return _empty_stats()
        database.init_db()
        placeholders = ",".join("?" for _ in document_ids)
        with database.get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT quality_score_before, quality_score_after, applied_at, auto_applied
                FROM subtitle_rewrite_suggestions
                WHERE document_id IN ({placeholders})
                """,
                document_ids,
            ).fetchall()
        improvements = [
            float(row["quality_score_after"]) - float(row["quality_score_before"])
            for row in rows
            if row["applied_at"] and row["quality_score_before"] is not None and row["quality_score_after"] is not None
        ]
        scored_rows = [row for row in rows if row["applied_at"]] or rows
        before_scores = [float(row["quality_score_before"]) for row in scored_rows if row["quality_score_before"] is not None]
        after_scores = [float(row["quality_score_after"]) for row in scored_rows if row["quality_score_after"] is not None]
        return {
            "suggestions_created": len(rows),
            "suggestions_applied": sum(1 for row in rows if row["applied_at"]),
            "auto_applied": sum(1 for row in rows if row["auto_applied"]),
            "average_quality_improvement": round(sum(improvements) / len(improvements), 4) if improvements else 0.0,
            "average_score_before": round(sum(before_scores) / len(before_scores), 4) if before_scores else 0.0,
            "average_score_after": round(sum(after_scores) / len(after_scores), 4) if after_scores else 0.0,
        }


def _values(suggestion: SubtitleRewriteSuggestion) -> tuple[Any, ...]:
    return (
        suggestion.id,
        suggestion.document_id,
        suggestion.line_index,
        suggestion.source_text,
        suggestion.original_translation,
        suggestion.suggested_text,
        suggestion.style.value,
        suggestion.reason,
        suggestion.char_count_before,
        suggestion.char_count_after,
        suggestion.estimated_cps_before,
        suggestion.estimated_cps_after,
        json.dumps(suggestion.safety_warnings, ensure_ascii=False),
        suggestion.quality_score_before,
        suggestion.quality_score_after,
        suggestion.created_at,
        suggestion.applied_at,
        int(suggestion.auto_applied),
    )


def _row_to_suggestion(row: Any) -> SubtitleRewriteSuggestion:
    return SubtitleRewriteSuggestion(
        id=row["id"],
        document_id=row["document_id"],
        line_index=int(row["line_index"]),
        source_text=row["source_text"],
        original_translation=row["original_translation"],
        suggested_text=row["suggested_text"],
        style=row["style"],
        reason=row["reason"],
        char_count_before=int(row["char_count_before"]),
        char_count_after=int(row["char_count_after"]),
        estimated_cps_before=row["estimated_cps_before"],
        estimated_cps_after=row["estimated_cps_after"],
        safety_warnings=json.loads(row["safety_warnings_json"] or "[]"),
        quality_score_before=row["quality_score_before"],
        quality_score_after=row["quality_score_after"],
        created_at=row["created_at"],
        applied_at=row["applied_at"] if "applied_at" in row.keys() else None,
        auto_applied=bool(row["auto_applied"]) if "auto_applied" in row.keys() else False,
    )


def _empty_stats() -> dict[str, float | int]:
    return {
        "suggestions_created": 0,
        "suggestions_applied": 0,
        "auto_applied": 0,
        "average_quality_improvement": 0.0,
        "average_score_before": 0.0,
        "average_score_after": 0.0,
    }
