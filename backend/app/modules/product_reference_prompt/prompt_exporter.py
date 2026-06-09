from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.modules.product_reference_prompt.reference_schema import VideoPromptPack
from app.utils.file_utils import ensure_dir, write_json


class PromptExporter:
    def export_prompt_pack(
        self,
        prompt_pack: VideoPromptPack,
        output_dir: str,
    ) -> dict[str, str]:
        target = ensure_dir(output_dir)
        files = {
            "product_reference_summary": target / "product_reference_summary.json",
            "storyboard_5_scenes": target / "storyboard_5_scenes.json",
            "video_prompt_full": target / "video_prompt_full.txt",
            "video_prompt_short": target / "video_prompt_short.txt",
            "video_prompt_pack_json": target / "video_prompt_pack.json",
            "negative_prompt": target / "negative_prompt.txt",
            "prompt_pack_generation_log": target / "prompt_pack_generation_log.json",
        }

        write_json(
            files["product_reference_summary"],
            prompt_pack.product_reference_summary.model_dump(mode="json"),
        )
        write_json(files["storyboard_5_scenes"], prompt_pack.storyboard.model_dump(mode="json"))
        files["video_prompt_full"].write_text(prompt_pack.video_prompt, encoding="utf-8")
        files["video_prompt_short"].write_text(prompt_pack.short_prompt or "", encoding="utf-8")
        write_json(files["video_prompt_pack_json"], prompt_pack.model_dump(mode="json"))
        files["negative_prompt"].write_text(prompt_pack.negative_prompt, encoding="utf-8")

        log_payload = {
            "project_id": prompt_pack.project_id,
            "product_name": prompt_pack.product_name,
            "duration_seconds": prompt_pack.storyboard.total_duration_seconds,
            "scene_count": len(prompt_pack.storyboard.scenes),
            "reference_assets_used": len(prompt_pack.product_reference_summary.reference_assets),
            "main_product_asset_id": prompt_pack.product_reference_summary.main_product_asset_id,
            "warnings": prompt_pack.product_reference_summary.warnings,
            "files": {key: str(path) for key, path in files.items() if key != "prompt_pack_generation_log"},
        }
        write_json(files["prompt_pack_generation_log"], log_payload)
        _update_project_summary(target.parent, log_payload)
        return {key: str(path) for key, path in files.items()}


def _update_project_summary(project_output_dir: Path, log_payload: dict[str, Any]) -> None:
    summary_path = project_output_dir / "project_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}
    else:
        summary = {
            "project_name": project_output_dir.name,
            "output_folder": str(project_output_dir),
        }
    summary["prompt_pack"] = {
        "generated": True,
        "duration_seconds": log_payload["duration_seconds"],
        "scene_count": log_payload["scene_count"],
        "reference_assets_used": log_payload["reference_assets_used"],
        "main_product_asset_id": log_payload["main_product_asset_id"],
        "files": log_payload["files"],
    }
    write_json(summary_path, summary)
