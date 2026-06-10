from __future__ import annotations

from typing import Any

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.douyin_reup_presets.preset_registry import get_douyin_reup_preset, list_douyin_reup_presets
from app.modules.douyin_reup_presets.preset_schema import DouyinReupPreset


class DouyinReupPresetService:
    def list_presets(self) -> list[DouyinReupPreset]:
        return list_douyin_reup_presets()

    def get_preset(self, preset_id: str) -> DouyinReupPreset:
        preset = get_douyin_reup_preset(preset_id)
        if not preset:
            raise LookupError(f"Unknown Douyin reup preset: {preset_id}")
        return preset

    def apply_preset(
        self,
        preset_id: str,
        current_settings: DouyinReupSettings | dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> DouyinReupSettings:
        preset = self.get_preset(preset_id)
        payload = preset.settings.model_dump(mode="json")

        if current_settings:
            current = (
                current_settings.model_dump(mode="json")
                if isinstance(current_settings, DouyinReupSettings)
                else dict(current_settings)
            )
            for key in ("music_folder", "selected_video_paths", "max_videos"):
                value = current.get(key)
                if value not in (None, "", []):
                    payload[key] = value

        normalized_overrides = _normalize_overrides(overrides or {})
        payload.update(normalized_overrides)
        payload["enabled"] = True
        payload["preset_id"] = preset.id.value
        payload["preset_name"] = preset.name
        return DouyinReupSettings.model_validate(payload)


def _normalize_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "use_existing_srt_if_available": "use_sidecar_srt",
        "extract_embedded_subtitle_if_available": "use_embedded_subtitle",
        "bgm_folder": "music_folder",
    }
    normalized: dict[str, Any] = {}
    allowed = set(DouyinReupSettings.model_fields)
    for key, value in overrides.items():
        target_key = aliases.get(str(key), str(key))
        if value is None:
            continue
        if target_key == "process_mode" and value == "all_videos":
            value = "all"
        if target_key == "music_folder" and value == "":
            value = None
        if target_key in allowed:
            normalized[target_key] = value
    return normalized
