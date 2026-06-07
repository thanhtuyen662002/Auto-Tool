from __future__ import annotations

from app.modules.industry_presets.industry_preset_service import IndustryPresetService
from app.schemas.project_schema import ProjectConfig


def test_apply_tech_industry_sets_recommended_fields_without_overwriting_product_or_paths() -> None:
    config = _config()

    updated = IndustryPresetService().apply_preset_to_config(config, "tech_electronics")

    assert updated.product == config.product
    assert updated.source_folder == config.source_folder
    assert updated.output_folder == config.output_folder
    assert updated.render.output_count == config.render.output_count
    assert updated.render.duration == config.render.duration
    assert updated.industry and updated.industry.preset_id == "tech_electronics"
    assert updated.timeline.template_id == "product_showcase_clean"
    assert updated.visual_style.preset_id == "tech_dark_neon"
    assert updated.tts.voice == "vi-VN-NamMinhNeural"
    assert updated.script_variation.mode == "auto_mix"
    assert updated.script_variation.preferred_variant_ids[0] == "benefit_first"
    assert updated.effects.cut_intensity == 65


def test_apply_industry_can_skip_selected_groups() -> None:
    config = _config()

    updated = IndustryPresetService().apply_preset_to_config(
        config,
        "fast_sale_trending",
        apply_visual_style=False,
        apply_timeline=False,
        apply_script_variation=False,
        apply_tts_voice=False,
        apply_edit_strength=False,
    )

    assert updated.industry and updated.industry.preset_id == "fast_sale_trending"
    assert updated.timeline.template_id == config.timeline.template_id
    assert updated.visual_style.preset_id == config.visual_style.preset_id
    assert updated.tts.voice == config.tts.voice
    assert updated.script_variation.preferred_variant_ids == config.script_variation.preferred_variant_ids
    assert updated.effects == config.effects


def _config() -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "industry-service-test",
            "source_folder": "source",
            "output_folder": "output",
            "product": {
                "name": "Máy chiếu test",
                "brand": "KAW",
                "description": "Mô tả test",
                "features": ["Hỗ trợ 4K"],
                "cta": "Xem ngay",
            },
            "render": {
                "output_count": 3,
                "duration": 12,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "fps": 30,
            },
            "effects": {
                "cut_intensity": 70,
                "speed_variation": 30,
                "grain": 15,
                "zoom_motion": 25,
                "overlay_height": 33,
                "subtitle_size": 84,
            },
            "ai": {
                "text_model": "gemini-test",
                "tone": "friendly_reviewer",
                "language": "vi",
                "gemini_api_keys": [],
            },
            "timeline": {"template_id": "ugc_reviewer_natural"},
            "visual_style": {"preset_id": "clean_review_light", "custom_overrides": None},
            "script_variation": {"mode": "auto_mix", "preferred_variant_ids": []},
        }
    )

