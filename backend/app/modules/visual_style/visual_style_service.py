from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.cache.cache_service import CacheService
from app.modules.visual_style.overlay_asset_builder import build_style_preview_image
from app.modules.visual_style.style_registry import (
    DEFAULT_VISUAL_STYLE_ID,
    get_visual_style_preset,
    list_visual_style_presets,
)
from app.modules.visual_style.style_schema import OverlayStyle, SubtitleStyle, VisualStylePreset, VisualStyleSettings
from app.utils.app_paths import app_data_dir
from app.utils.file_utils import ensure_dir


class VisualStyleService:
    def list_presets(self) -> list[VisualStylePreset]:
        return list_visual_style_presets()

    def resolve_preset(self, settings: VisualStyleSettings | None) -> VisualStylePreset:
        settings = settings or VisualStyleSettings()
        preset = get_visual_style_preset(settings.preset_id)
        if not settings.custom_overrides:
            return preset
        return _apply_overrides(preset, settings.custom_overrides)

    def preview_style(
        self,
        preset_id: str,
        sample_text: str,
        resolution: str,
        output_dir: str | Path | None = None,
    ) -> str:
        width, height = parse_resolution(resolution)
        preset = get_visual_style_preset(preset_id or DEFAULT_VISUAL_STYLE_ID)
        target_dir = ensure_dir(output_dir or app_data_dir() / "style_previews")
        safe_text = sample_text.strip() or "Nhỏ gọn, dễ dùng, phù hợp mỗi ngày"
        cache_service = CacheService(target_dir / ".cache")
        cache_key = cache_service.keys.build_style_preview_key(preset.id, f"{width}x{height}", safe_text)
        key_suffix = cache_key.rsplit("/", 1)[-1][:12]
        output_path = target_dir / f"style_preview_{preset.id}_{width}x{height}_{key_suffix}.png"
        cached = cache_service.get_file("style_previews", cache_key, output_path)
        if cached:
            return cached

        result = build_style_preview_image(preset, safe_text, width, height, str(output_path))
        cache_service.set_file(cache_key, result)
        return result


def parse_resolution(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        parsed = int(width), int(height)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Resolution phải dùng định dạng WIDTHxHEIGHT, ví dụ 1080x1920: {value}") from exc
    if parsed[0] <= 0 or parsed[1] <= 0:
        raise ValueError(f"Resolution phải lớn hơn 0: {value}")
    return parsed


def _apply_overrides(preset: VisualStylePreset, overrides: dict[str, Any]) -> VisualStylePreset:
    subtitle = preset.subtitle
    overlay = preset.overlay
    if isinstance(overrides.get("subtitle"), dict):
        subtitle = SubtitleStyle.model_validate({**subtitle.model_dump(mode="json"), **overrides["subtitle"]})
    if isinstance(overrides.get("overlay"), dict):
        overlay = OverlayStyle.model_validate({**overlay.model_dump(mode="json"), **overrides["overlay"]})
    return preset.model_copy(update={"subtitle": subtitle, "overlay": overlay})
