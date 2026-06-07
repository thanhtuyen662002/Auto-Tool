from __future__ import annotations

from app.modules.industry_presets.industry_registry import (
    DEFAULT_INDUSTRY_PRESET_ID,
    get_industry_preset,
    list_industry_presets,
)


def test_industry_registry_has_required_presets() -> None:
    presets = list_industry_presets()
    ids = {preset.id for preset in presets}

    assert len(presets) >= 8
    assert {
        "general_product",
        "tech_electronics",
        "beauty_cosmetics",
        "fashion_accessories",
        "home_lifestyle",
        "mom_baby",
        "food_beverage",
        "fast_sale_trending",
    }.issubset(ids)


def test_unknown_industry_falls_back_to_general_product() -> None:
    preset = get_industry_preset("missing")

    assert preset.id == DEFAULT_INDUSTRY_PRESET_ID
    assert preset.timeline_template_id == "ugc_reviewer_natural"

