from __future__ import annotations

from app.modules.industry_presets.industry_registry import (
    DEFAULT_INDUSTRY_PRESET_ID,
    get_industry_preset,
    list_industry_presets,
)
from app.modules.industry_presets.industry_schema import IndustryPreset, IndustrySettings
from app.schemas.project_schema import EffectSettings, ProjectConfig


EDIT_STRENGTH_EFFECTS: dict[str, dict[str, int]] = {
    "nhẹ": {
        "cut_intensity": 35,
        "speed_variation": 15,
        "grain": 5,
        "zoom_motion": 10,
        "overlay_height": 20,
        "subtitle_size": 52,
    },
    "vừa": {
        "cut_intensity": 65,
        "speed_variation": 30,
        "grain": 12,
        "zoom_motion": 20,
        "overlay_height": 22,
        "subtitle_size": 54,
    },
    "mạnh": {
        "cut_intensity": 85,
        "speed_variation": 55,
        "grain": 18,
        "zoom_motion": 35,
        "overlay_height": 24,
        "subtitle_size": 56,
    },
}


class IndustryPresetService:
    def list_presets(self) -> list[IndustryPreset]:
        return list_industry_presets()

    def get_preset(self, preset_id: str | None) -> IndustryPreset:
        return get_industry_preset(preset_id or DEFAULT_INDUSTRY_PRESET_ID)

    def apply_preset_to_config(
        self,
        config: ProjectConfig,
        preset_id: str,
        *,
        apply_visual_style: bool = True,
        apply_timeline: bool = True,
        apply_script_variation: bool = True,
        apply_tts_voice: bool = True,
        apply_edit_strength: bool = True,
    ) -> ProjectConfig:
        preset = self.get_preset(preset_id)
        updates: dict[str, object] = {
            "industry": IndustrySettings(preset_id=preset.id),
        }

        if apply_timeline:
            updates["timeline"] = config.timeline.model_copy(update={"template_id": preset.timeline_template_id})

        if apply_visual_style:
            updates["visual_style"] = config.visual_style.model_copy(
                update={"preset_id": preset.visual_style_preset_id, "custom_overrides": None}
            )

        if apply_tts_voice:
            updates["tts"] = config.tts.model_copy(update={"voice": preset.default_tts_voice})

        if apply_script_variation:
            updates["script_variation"] = config.script_variation.model_copy(
                update={
                    "mode": preset.script_variation_mode,
                    "preferred_variant_ids": list(preset.preferred_script_variant_ids),
                }
            )

        if apply_edit_strength:
            effects = _effects_for_strength(preset.default_edit_strength)
            if effects is not None:
                updates["effects"] = effects

        return config.model_copy(update=updates)


def _effects_for_strength(strength: str) -> EffectSettings | None:
    key = strength.strip().lower()
    values = EDIT_STRENGTH_EFFECTS.get(key)
    if values is None:
        return None
    return EffectSettings.model_validate(values)

