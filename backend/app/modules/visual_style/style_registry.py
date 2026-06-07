from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.modules.visual_style.style_schema import OverlayStyle, SubtitleStyle, VisualStylePreset


DEFAULT_VISUAL_STYLE_ID = "clean_review_light"


_PRESET_DATA: list[dict[str, Any]] = [
    {
        "id": "clean_review_light",
        "name": "Review sạch dễ đọc",
        "description": "Overlay tối nhẹ, subtitle trắng rõ, phù hợp hầu hết video review sản phẩm.",
        "category": "review",
        "recommended_for": ["review", "general", "product"],
        "overlay": {
            "height_ratio": 0.22,
            "background_color": "#111111",
            "background_opacity": 0.58,
            "border_radius": 28,
            "show_soft_gradient": True,
        },
        "subtitle": {
            "font_size": 54,
            "font_color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 2,
            "max_chars_per_line": 22,
            "max_lines": 2,
        },
    },
    {
        "id": "cute_pastel_shop",
        "name": "Dễ thương pastel",
        "description": "Panel pastel sáng, accent hồng, hợp mẹ và bé, mỹ phẩm và đồ gia dụng nhỏ.",
        "category": "cute",
        "recommended_for": ["mom_baby", "beauty", "small_home"],
        "overlay": {
            "height_ratio": 0.24,
            "background_color": "#FFF2F6",
            "background_opacity": 0.88,
            "border_radius": 36,
            "accent_color": "#FF7AAE",
            "show_accent_bar": True,
            "show_soft_gradient": False,
        },
        "subtitle": {
            "font_size": 52,
            "font_color": "#2B2B2B",
            "stroke_color": "#FFFFFF",
            "stroke_width": 1,
            "max_chars_per_line": 21,
            "max_lines": 2,
        },
    },
    {
        "id": "tech_dark_neon",
        "name": "Công nghệ dark neon",
        "description": "Panel tối, accent xanh neon, hợp máy chiếu và phụ kiện điện tử.",
        "category": "tech",
        "recommended_for": ["tech", "electronics", "projector"],
        "overlay": {
            "height_ratio": 0.22,
            "background_color": "#050816",
            "background_opacity": 0.78,
            "border_radius": 24,
            "accent_color": "#35D4FF",
            "show_accent_bar": True,
            "show_soft_gradient": True,
        },
        "subtitle": {
            "font_size": 54,
            "font_color": "#FFFFFF",
            "stroke_color": "#0B0B0B",
            "stroke_width": 2,
            "max_chars_per_line": 22,
            "max_lines": 2,
        },
    },
    {
        "id": "beauty_soft_glow",
        "name": "Làm đẹp soft glow",
        "description": "Màu sáng ấm, mềm, hợp mỹ phẩm, làm đẹp và thời trang nữ.",
        "category": "beauty",
        "recommended_for": ["beauty", "skincare", "fashion"],
        "overlay": {
            "height_ratio": 0.23,
            "background_color": "#FFF7F0",
            "background_opacity": 0.86,
            "border_radius": 34,
            "accent_color": "#E9A7C0",
            "show_accent_bar": True,
            "show_soft_gradient": True,
        },
        "subtitle": {
            "font_size": 52,
            "font_color": "#3A2A2A",
            "stroke_color": "#FFFFFF",
            "stroke_width": 1,
            "max_chars_per_line": 21,
            "max_lines": 2,
        },
    },
    {
        "id": "food_warm_label",
        "name": "Đồ ăn ấm áp",
        "description": "Tone ấm, dễ đọc, hợp đồ ăn, đồ uống, coffee và gia vị.",
        "category": "food",
        "recommended_for": ["food", "drink", "coffee"],
        "overlay": {
            "height_ratio": 0.23,
            "background_color": "#FFF0D7",
            "background_opacity": 0.88,
            "border_radius": 32,
            "accent_color": "#FF8A00",
            "show_accent_bar": True,
            "show_soft_gradient": False,
        },
        "subtitle": {
            "font_size": 52,
            "font_color": "#3A2412",
            "stroke_color": "#FFFFFF",
            "stroke_width": 1,
            "max_chars_per_line": 21,
            "max_lines": 2,
        },
    },
    {
        "id": "sale_bold_red",
        "name": "Sale nổi bật",
        "description": "Đỏ mạnh, accent vàng, hợp video sale nhanh và CTA rõ.",
        "category": "sale",
        "recommended_for": ["sale", "fast_tiktok", "promotion"],
        "overlay": {
            "height_ratio": 0.24,
            "background_color": "#B00020",
            "background_opacity": 0.82,
            "border_radius": 24,
            "accent_color": "#FFD54A",
            "show_accent_bar": True,
            "show_soft_gradient": True,
        },
        "subtitle": {
            "font_size": 56,
            "font_color": "#FFFFFF",
            "stroke_color": "#4A000A",
            "stroke_width": 2,
            "max_chars_per_line": 20,
            "max_lines": 2,
        },
    },
    {
        "id": "fashion_minimal",
        "name": "Thời trang tối giản",
        "description": "Panel sáng tối giản, hợp thời trang, áo khoác và phụ kiện.",
        "category": "fashion",
        "recommended_for": ["fashion", "accessory", "jacket"],
        "overlay": {
            "height_ratio": 0.21,
            "background_color": "#F7F3EE",
            "background_opacity": 0.84,
            "border_radius": 26,
            "accent_color": "#1E1E1E",
            "show_accent_bar": False,
            "show_soft_gradient": False,
        },
        "subtitle": {
            "font_size": 52,
            "font_color": "#1E1E1E",
            "stroke_color": "#FFFFFF",
            "stroke_width": 1,
            "max_chars_per_line": 22,
            "max_lines": 2,
        },
    },
    {
        "id": "transparent_caption_box",
        "name": "Khung trong suốt nhẹ",
        "description": "Overlay thấp và trong hơn, dùng khi cần thấy nhiều sản phẩm trong video.",
        "category": "minimal",
        "recommended_for": ["showcase", "product", "minimal"],
        "overlay": {
            "height_ratio": 0.18,
            "background_color": "#000000",
            "background_opacity": 0.38,
            "border_radius": 22,
            "show_accent_bar": False,
            "show_soft_gradient": False,
        },
        "subtitle": {
            "font_size": 50,
            "font_color": "#FFFFFF",
            "stroke_color": "#000000",
            "stroke_width": 2,
            "max_chars_per_line": 24,
            "max_lines": 2,
        },
    },
]


def list_visual_style_presets() -> list[VisualStylePreset]:
    return [_preset_from_data(data) for data in _PRESET_DATA]


def get_visual_style_preset(preset_id: str | None) -> VisualStylePreset:
    lookup = (preset_id or DEFAULT_VISUAL_STYLE_ID).strip()
    for data in _PRESET_DATA:
        if data["id"] == lookup:
            return _preset_from_data(data)
    return _preset_from_data(next(data for data in _PRESET_DATA if data["id"] == DEFAULT_VISUAL_STYLE_ID))


def visual_style_exists(preset_id: str) -> bool:
    return any(data["id"] == preset_id for data in _PRESET_DATA)


def _preset_from_data(data: dict[str, Any]) -> VisualStylePreset:
    payload = deepcopy(data)
    overlay = OverlayStyle.model_validate(payload.pop("overlay"))
    subtitle = SubtitleStyle.model_validate(payload.pop("subtitle"))
    return VisualStylePreset.model_validate({**payload, "overlay": overlay, "subtitle": subtitle})
