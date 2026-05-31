from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from app.modules.content_manager.content_schema import (
    ContentBatchSummary,
    OutputContentItem,
    build_content_summary,
)
from app.utils.file_utils import ensure_dir


SUPPORTED_EXPORT_FORMATS = {"json", "csv", "txt", "md"}


class ContentExporter:
    def export(
        self,
        items: list[OutputContentItem],
        output_dir: str | Path,
        formats: Iterable[str] | None = None,
    ) -> dict[str, str]:
        target_dir = ensure_dir(output_dir)
        selected = _normalize_formats(formats)
        summary = build_content_summary(items)
        paths: dict[str, str] = {}

        content_items_path = target_dir / "content_items.json"
        _write_json(content_items_path, _items_payload(items, summary))
        paths["content_items"] = str(content_items_path)

        if "json" in selected:
            json_path = target_dir / "content_export.json"
            _write_json(json_path, _items_payload(items, summary))
            paths["json"] = str(json_path)
        if "csv" in selected:
            csv_path = target_dir / "content_export.csv"
            _write_csv(csv_path, items)
            paths["csv"] = str(csv_path)
        if "txt" in selected:
            txt_path = target_dir / "content_export.txt"
            txt_path.write_text(_txt_content(items), encoding="utf-8")
            paths["txt"] = str(txt_path)
        if "md" in selected:
            md_path = target_dir / "content_plan.md"
            md_path.write_text(_markdown_content(items, summary), encoding="utf-8")
            paths["md"] = str(md_path)

        return paths


def _normalize_formats(formats: Iterable[str] | None) -> set[str]:
    if formats is None:
        return set(SUPPORTED_EXPORT_FORMATS)
    selected = {str(item).strip().lower() for item in formats if str(item).strip()}
    invalid = selected - SUPPORTED_EXPORT_FORMATS
    if invalid:
        raise ValueError(f"Định dạng export không được hỗ trợ: {', '.join(sorted(invalid))}")
    return selected or set(SUPPORTED_EXPORT_FORMATS)


def _items_payload(items: list[OutputContentItem], summary: ContentBatchSummary) -> dict:
    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "summary": summary.model_dump(mode="json"),
        "items": [item.model_dump(mode="json") for item in items],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, items: list[OutputContentItem]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "output_index",
                "publish_status",
                "platform",
                "video_path",
                "hook",
                "caption",
                "hashtags",
                "cta",
                "variant_style_id",
                "timeline_template_id",
                "user_note",
            ],
        )
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "output_index": item.output_index,
                    "publish_status": item.publish_status.value,
                    "platform": item.platform or "",
                    "video_path": item.video_path,
                    "hook": item.hook or "",
                    "caption": item.caption,
                    "hashtags": " ".join(item.hashtags),
                    "cta": item.cta or "",
                    "variant_style_id": item.variant_style_id or "",
                    "timeline_template_id": item.timeline_template_id or "",
                    "user_note": item.user_note or "",
                }
            )


def _txt_content(items: list[OutputContentItem]) -> str:
    blocks: list[str] = []
    for item in items:
        blocks.append(
            "\n".join(
                [
                    f"Video {item.output_index:03d}",
                    f"Trạng thái: {item.publish_status.value}",
                    f"Video: {item.video_path}",
                    "",
                    item.caption,
                    " ".join(item.hashtags),
                    "",
                    f"CTA: {item.cta or ''}".rstrip(),
                    f"Ghi chú: {item.user_note or ''}".rstrip(),
                ]
            ).strip()
        )
    return "\n\n---\n\n".join(blocks) + ("\n" if blocks else "")


def _markdown_content(items: list[OutputContentItem], summary: ContentBatchSummary) -> str:
    lines = [
        "# Content Plan",
        "",
        f"- Tổng nội dung: {summary.total_items}",
        f"- Nháp: {summary.draft}",
        f"- Đã sao chép: {summary.copied}",
        f"- Đã đăng: {summary.posted}",
        f"- Bỏ qua: {summary.skipped}",
        "",
        "| Video | Trạng thái | Caption | Hashtags | Ghi chú |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            "| "
            f"{item.output_index:03d} | "
            f"{item.publish_status.value} | "
            f"{_escape_md(item.caption)} | "
            f"{_escape_md(' '.join(item.hashtags))} | "
            f"{_escape_md(item.user_note or '')} |"
        )
    return "\n".join(lines) + "\n"


def _escape_md(value: str) -> str:
    return " ".join(value.replace("|", "\\|").split())

