from __future__ import annotations

import json

from app.modules.content_manager.content_exporter import ContentExporter
from app.modules.content_manager.content_schema import OutputContentItem


def test_content_exporter_writes_all_supported_formats(tmp_path):
    item = OutputContentItem(
        id="project:content:1",
        project_id="project",
        output_index=1,
        video_path=str(tmp_path / "video_001.mp4"),
        hook="Hook",
        caption="Caption tiếng Việt",
        hashtags=["#review", "#sanpham"],
        cta="Xem chi tiết",
        variant_style_id="reviewer_natural",
        timeline_template_id="ugc_reviewer_natural",
        publish_status="draft",
        platform=None,
        user_note="Ghi chú",
        created_at="2026-05-31T10:00:00",
        updated_at="2026-05-31T10:00:00",
    )

    files = ContentExporter().export([item], tmp_path, ["json", "csv", "txt", "md"])

    assert (tmp_path / "content_items.json").exists()
    assert set(files) == {"content_items", "json", "csv", "txt", "md"}
    assert json.loads((tmp_path / "content_export.json").read_text(encoding="utf-8"))["summary"]["total_items"] == 1
    assert "Caption tiếng Việt" in (tmp_path / "content_export.csv").read_text(encoding="utf-8-sig")
    assert "#review #sanpham" in (tmp_path / "content_export.txt").read_text(encoding="utf-8")
    assert "| 001 | draft |" in (tmp_path / "content_plan.md").read_text(encoding="utf-8")


def test_content_exporter_rejects_unknown_format(tmp_path):
    try:
        ContentExporter().export([], tmp_path, ["xlsx"])
    except ValueError as exc:
        assert "xlsx" in str(exc)
    else:
        raise AssertionError("Expected invalid format to raise ValueError")

