from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.modules.timeline_templates.template_registry import template_id_for_preset


DEFAULT_RENDER_SETTINGS: dict[str, Any] = {
    "output_count": 3,
    "duration": 12,
    "aspect_ratio": "9:16",
    "resolution": "1080x1920",
    "fps": 30,
}

DEFAULT_EFFECT_SETTINGS: dict[str, int] = {
    "cut_intensity": 70,
    "speed_variation": 30,
    "grain": 15,
    "zoom_motion": 25,
    "overlay_height": 33,
    "subtitle_size": 84,
}

DEFAULT_PRESETS: list[dict[str, Any]] = [
    {
        "name": "Light Recut",
        "effects": {
            "cut_intensity": 30,
            "speed_variation": 10,
            "grain": 5,
            "zoom_motion": 10,
            "overlay_height": 22,
            "subtitle_size": 54,
        },
    },
    {
        "name": "Balanced Recut",
        "effects": {
            "cut_intensity": 70,
            "speed_variation": 30,
            "grain": 15,
            "zoom_motion": 25,
            "overlay_height": 22,
            "subtitle_size": 54,
        },
    },
    {
        "name": "Aggressive Remix",
        "effects": {
            "cut_intensity": 95,
            "speed_variation": 70,
            "grain": 25,
            "zoom_motion": 45,
            "overlay_height": 22,
            "subtitle_size": 54,
        },
    },
]


def get_default_presets() -> list[dict[str, Any]]:
    presets = deepcopy(DEFAULT_PRESETS)
    for preset in presets:
        preset["timeline_template_id"] = template_id_for_preset(preset["name"])
    return presets
