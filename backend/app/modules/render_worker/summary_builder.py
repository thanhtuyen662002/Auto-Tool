from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.modules.render_worker.output_log import base_name, short_message
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import write_json


def finalize_summary(summary: dict[str, Any]) -> None:
    outputs = summary.get("outputs", [])
    summary["total_outputs"] = summary.get("requested_outputs", len(outputs))
    summary["successful_outputs"] = sum(1 for item in outputs if item.get("status") in {"success", "warning"})
    summary["failed_outputs"] = sum(1 for item in outputs if item.get("status") == "failed")
    summary["warnings_count"] = sum(len(item.get("warnings", [])) for item in outputs)
    summary["failed_items"] = [
        {
            "index": item.get("index"),
            "reason": item.get("error") or (item.get("errors") or ["Unknown render failure"])[0],
        }
        for item in outputs
        if item.get("status") == "failed"
    ]
    summary["visual_style_summary"] = _visual_style_summary(outputs)


def failed_output_records(
    config: ProjectConfig,
    output_dir: Path,
    preview_only: bool,
    reason: str,
    start_index: int = 1,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if start_index > config.render.output_count:
        return records

    for index in range(start_index, config.render.output_count + 1):
        name = base_name(index, preview_only)
        final_path = output_dir / f"{name}.mp4"
        visual_path = output_dir / f"{name}_visual.mp4"
        script_path = output_dir / f"{name}_script.json"
        subtitle_path = output_dir / f"{name}_sub.srt"
        subtitle_ass_path = output_dir / f"{name}_sub.ass"
        voice_path = output_dir / f"{name}_voice.{_voice_extension(config)}"
        log_path = output_dir / f"{name}_log.json"
        now = datetime.now().replace(microsecond=0).isoformat()
        message = f"Could not prepare output {index:03d}: {reason}"
        output_log = {
            "index": index,
            "status": "failed",
            "started_at": now,
            "finished_at": now,
            "duration_seconds": 0,
            "steps": [
                {
                    "name": "prepare_project",
                    "status": "failed",
                    "message": message,
                }
            ],
            "visual_video": str(visual_path),
            "final_video": str(final_path),
            "script_file": str(script_path),
            "subtitle_file": str(subtitle_path),
            "subtitle_ass_file": str(subtitle_ass_path),
            "voice_file": str(voice_path),
            "music_file": None,
            "visual_style": {
                "preset_id": config.visual_style.preset_id,
                "overlay_asset": str(output_dir / f"{name}_overlay.png"),
                "subtitle_format": "none",
                "ass_subtitle_path": str(subtitle_ass_path),
                "fallback_used": True,
                "warnings": ["prepare_project_failed"],
            },
            "performance": {"total_seconds": 0},
            "warnings": [],
            "errors": [message],
            "error": message,
        }
        write_json(log_path, output_log)
        records.append(
            {
                "index": index,
                "path": str(final_path),
                "status": "failed",
                "duration": None,
                "error": short_message(message),
                "warnings": [],
                "errors": [short_message(message)],
                "visual_video": str(visual_path),
                "script_file": str(script_path),
                "subtitle_file": str(subtitle_path),
                "subtitle_ass_file": str(subtitle_ass_path),
                "overlay_file": str(output_dir / f"{name}_overlay.png"),
                "voice_file": str(voice_path),
                "music_file": None,
                "timeline_template": config.timeline.template_id,
                "script_variant_id": None,
                "caption": None,
                "hashtags": [],
                "log_file": str(log_path),
                "visual_style": {
                    "preset_id": config.visual_style.preset_id,
                    "overlay_asset": str(output_dir / f"{name}_overlay.png"),
                    "subtitle_format": "none",
                    "ass_subtitle_path": str(subtitle_ass_path),
                    "fallback_used": True,
                    "warnings": ["prepare_project_failed"],
                },
                "performance": {"total_seconds": 0},
            }
        )
    return records


def _voice_extension(config: ProjectConfig) -> str:
    provider = config.tts.provider.strip().lower().replace("-", "_")
    output_format = config.tts.output_format.strip().lower().lstrip(".")
    if provider == "piper":
        return "wav"
    if output_format in {"mp3", "wav"}:
        return output_format
    return "mp3"


def _visual_style_summary(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    preset_id = None
    outputs_rendered_with_ass = 0
    outputs_fallback_to_srt = 0
    outputs_fallback_to_drawbox = 0
    for output in outputs:
        visual_style = output.get("visual_style") or {}
        if not isinstance(visual_style, dict):
            continue
        preset_id = preset_id or visual_style.get("preset_id")
        subtitle_format = visual_style.get("subtitle_format")
        warnings = [str(item) for item in visual_style.get("warnings", [])]
        if subtitle_format == "ass" and not visual_style.get("fallback_used"):
            outputs_rendered_with_ass += 1
        if subtitle_format == "srt" or any("srt" in warning for warning in warnings):
            outputs_fallback_to_srt += 1
        if any("drawbox" in warning for warning in warnings):
            outputs_fallback_to_drawbox += 1
    return {
        "preset_id": preset_id,
        "outputs_rendered_with_ass": outputs_rendered_with_ass,
        "outputs_fallback_to_srt": outputs_fallback_to_srt,
        "outputs_fallback_to_drawbox": outputs_fallback_to_drawbox,
    }
