from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app import database
from app.modules.content_manager.content_exporter import ContentExporter
from app.modules.content_manager.content_schema import (
    OutputContentItem,
    PublishStatus,
    build_content_summary,
    normalize_hashtags,
)
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import ProjectConfig


class ContentService:
    def build_content_items_from_outputs(self, project_id: str) -> list[OutputContentItem]:
        project = database.get_project(project_id)
        if not project:
            raise ValueError(f"Không tìm thấy project: {project_id}")

        config = ProjectConfig.model_validate(project["config"])
        outputs = _latest_outputs_by_index(project_id)
        if not outputs:
            return []

        items: list[OutputContentItem] = []
        for output_index in sorted(outputs):
            output = outputs[output_index]
            video_path = str(output.get("path") or "").strip()
            if not video_path:
                continue

            existing = database.get_output_content_item(project_id, output_index)
            source_item = _content_item_from_output(project_id, config, output_index, output)
            if existing:
                source_item = _merge_existing_edits(source_item, existing)

            saved = database.upsert_output_content_item(source_item)
            items.append(OutputContentItem.model_validate(saved))

        self.write_content_items_file(project_id, items)
        return items

    def get_content_items(self, project_id: str) -> list[OutputContentItem]:
        project = database.get_project(project_id)
        if not project:
            raise ValueError(f"Không tìm thấy project: {project_id}")

        self.build_content_items_from_outputs(project_id)
        rows = database.list_output_content_items(project_id)
        return [OutputContentItem.model_validate(row) for row in rows]

    def update_content_item(
        self,
        project_id: str,
        output_index: int,
        data: dict[str, Any],
    ) -> OutputContentItem:
        if output_index <= 0:
            raise ValueError("output_index phải lớn hơn 0.")

        if not database.get_output_content_item(project_id, output_index):
            self.build_content_items_from_outputs(project_id)

        existing = database.get_output_content_item(project_id, output_index)
        if not existing:
            raise ValueError(f"Không tìm thấy nội dung cho video {output_index:03d}.")

        updates = _clean_update_payload(data)
        merged = {**existing, **updates}
        validated = OutputContentItem.model_validate(merged)
        saved = database.update_output_content_item(
            project_id,
            output_index,
            validated.model_dump(mode="json"),
        )
        if not saved:
            raise ValueError(f"Không thể cập nhật nội dung cho video {output_index:03d}.")

        items = [OutputContentItem.model_validate(row) for row in database.list_output_content_items(project_id)]
        self.write_content_items_file(project_id, items)
        return OutputContentItem.model_validate(saved)

    def mark_copied(self, project_id: str, output_index: int) -> OutputContentItem:
        return self.update_content_item(
            project_id,
            output_index,
            {"publish_status": PublishStatus.copied.value},
        )

    def mark_posted(self, project_id: str, output_index: int, platform: str | None = None) -> OutputContentItem:
        updates: dict[str, Any] = {"publish_status": PublishStatus.posted.value}
        if platform is not None:
            updates["platform"] = platform
        return self.update_content_item(project_id, output_index, updates)

    def export_content(self, project_id: str, formats: list[str] | None = None) -> dict[str, str]:
        items = self.get_content_items(project_id)
        output_dir = _latest_output_folder(project_id)
        if output_dir is None:
            project = database.get_project(project_id)
            if not project:
                raise ValueError(f"Không tìm thấy project: {project_id}")
            output_dir = Path(ProjectConfig.model_validate(project["config"]).output_folder)
        return ContentExporter().export(items, output_dir, formats)

    def write_content_items_file(self, project_id: str, items: list[OutputContentItem]) -> str | None:
        output_dir = _latest_output_folder(project_id)
        if output_dir is None:
            return None
        payload = {
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "summary": build_content_summary(items).model_dump(mode="json"),
            "items": [item.model_dump(mode="json") for item in items],
        }
        path = output_dir / "content_items.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


def _latest_outputs_by_index(project_id: str) -> dict[int, dict[str, Any]]:
    jobs = database.get_project_jobs(project_id, include_preview=False)
    if not jobs:
        jobs = database.get_project_jobs(project_id, include_preview=True)

    outputs: dict[int, dict[str, Any]] = {}
    for job in jobs:
        for output in job.get("results", {}).get("outputs", []):
            if not isinstance(output, dict):
                continue
            try:
                output_index = int(output["index"])
            except (KeyError, TypeError, ValueError):
                continue
            outputs[output_index] = output
    return outputs


def _latest_output_folder(project_id: str) -> Path | None:
    jobs = database.get_project_jobs(project_id, include_preview=False)
    if not jobs:
        jobs = database.get_project_jobs(project_id, include_preview=True)
    for job in reversed(jobs):
        output_folder = job.get("output_folder")
        if output_folder:
            return Path(output_folder)
    return None


def _content_item_from_output(
    project_id: str,
    config: ProjectConfig,
    output_index: int,
    output: dict[str, Any],
) -> dict[str, Any]:
    script = _read_script(output.get("script_file"))
    timeline = _read_json(output.get("timeline_file"))
    fallback_caption = config.product.description or config.product.name
    caption = _first_text(
        script.caption if script else None,
        output.get("caption"),
        fallback_caption,
        "Nội dung sản phẩm cần được bổ sung.",
    )
    hashtags = normalize_hashtags(
        script.hashtags if script else output.get("hashtags") or ["#review", "#sanpham", "#muasam"]
    )
    cta = _first_text(script.cta if script else None, output.get("cta"), config.product.cta)
    return {
        "id": f"{project_id}:content:{output_index}",
        "project_id": project_id,
        "output_index": output_index,
        "video_path": str(output.get("path") or ""),
        "hook": _first_optional(script.hook if script else None, output.get("hook")),
        "caption": caption,
        "hashtags": hashtags,
        "cta": cta,
        "variant_style_id": _first_optional(
            output.get("script_variant_id"),
            script.variant_style_id if script else None,
        ),
        "timeline_template_id": _first_optional(
            output.get("timeline_template"),
            timeline.get("template_id"),
        ),
        "publish_status": PublishStatus.draft.value,
        "platform": None,
        "user_note": None,
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
        "updated_at": datetime.now().replace(microsecond=0).isoformat(),
    }


def _merge_existing_edits(source_item: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    merged = dict(source_item)
    for key in ("caption", "hashtags", "cta", "publish_status", "platform", "user_note"):
        if existing.get(key) is not None:
            merged[key] = existing[key]
    merged["id"] = existing["id"]
    merged["created_at"] = existing["created_at"]
    return merged


def _clean_update_payload(data: dict[str, Any]) -> dict[str, Any]:
    updates = dict(data)
    if "hashtags" in updates:
        updates["hashtags"] = normalize_hashtags(updates["hashtags"])
    if "publish_status" in updates and isinstance(updates["publish_status"], PublishStatus):
        updates["publish_status"] = updates["publish_status"].value
    for key in ("hook", "caption", "cta", "variant_style_id", "timeline_template_id", "platform", "user_note"):
        if key in updates and updates[key] is not None:
            updates[key] = str(updates[key]).strip()
    return updates


def _read_script(path_value: Any) -> ProductVideoScript | None:
    payload = _read_json(path_value)
    if not payload:
        return None
    try:
        return ProductVideoScript.model_validate(payload)
    except Exception:
        return None


def _read_json(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    try:
        path = Path(str(path_value))
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        cleaned = " ".join(str(value).split())
        if cleaned:
            return cleaned
    return "Nội dung sản phẩm cần được bổ sung."


def _first_optional(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None
