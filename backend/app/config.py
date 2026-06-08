from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.project_schema import ProjectConfig
from app.utils.path_utils import resolve_path


def _format_validation_error(error: ValidationError) -> str:
    lines = ["Invalid project config:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", []))
        message = item.get("msg", "invalid value")
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def load_project_config(config_path: str) -> ProjectConfig:
    config_file = Path(config_path).expanduser().resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Config file does not exist: {config_file}")

    try:
        raw_data = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {config_file}\n{exc}") from exc

    try:
        config = ProjectConfig.model_validate(raw_data)
    except ValidationError as exc:
        raise ValueError(_format_validation_error(exc)) from exc

    base_dir = config_file.parent
    music_updates = {}
    if config.music.source_folder:
        music_updates["source_folder"] = str(resolve_path(config.music.source_folder, base_dir, must_exist=True))
    if config.music.source_file:
        music_updates["source_file"] = str(resolve_path(config.music.source_file, base_dir, must_exist=True))

    music = config.music.model_copy(update=music_updates) if music_updates else config.music
    visual_style_updates = {}
    if config.visual_style.overlay_mode == "custom" and config.visual_style.custom_overlay_path:
        visual_style_updates["custom_overlay_path"] = str(
            resolve_path(config.visual_style.custom_overlay_path, base_dir, must_exist=True)
        )
    visual_style = (
        config.visual_style.model_copy(update=visual_style_updates)
        if visual_style_updates
        else config.visual_style
    )
    return config.model_copy(
        update={
            "source_folder": str(resolve_path(config.source_folder, base_dir, must_exist=True)),
            "output_folder": str(resolve_path(config.output_folder, base_dir)),
            "music": music,
            "visual_style": visual_style,
        }
    )
