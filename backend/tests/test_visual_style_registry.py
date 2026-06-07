from __future__ import annotations

from app.modules.visual_style.style_registry import (
    DEFAULT_VISUAL_STYLE_ID,
    get_visual_style_preset,
    list_visual_style_presets,
)


def test_default_visual_style_registry_has_required_presets() -> None:
    presets = list_visual_style_presets()
    preset_ids = {preset.id for preset in presets}

    assert len(presets) >= 8
    assert DEFAULT_VISUAL_STYLE_ID in preset_ids
    assert {
        "clean_review_light",
        "cute_pastel_shop",
        "tech_dark_neon",
        "beauty_soft_glow",
        "food_warm_label",
        "sale_bold_red",
        "fashion_minimal",
        "transparent_caption_box",
    }.issubset(preset_ids)


def test_unknown_visual_style_falls_back_to_default() -> None:
    preset = get_visual_style_preset("missing-style")

    assert preset.id == DEFAULT_VISUAL_STYLE_ID
    assert preset.overlay.height_ratio > 0
    assert preset.subtitle.font_size > 0
