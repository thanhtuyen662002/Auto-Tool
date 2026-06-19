from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubtitleStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_family: str = "Arial"
    font_size: int = Field(default=54, ge=18, le=120)
    font_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = Field(default=2, ge=0, le=12)
    shadow_enabled: bool = True
    shadow_color: str = "#000000"
    shadow_opacity: float = Field(default=0.35, ge=0.0, le=1.0)
    shadow_size: int = Field(default=2, ge=0, le=12)
    max_chars_per_line: int = Field(default=22, ge=10, le=48)
    max_lines: int = Field(default=2, ge=1, le=3)
    position: str = "bottom_overlay"

    @field_validator("font_color", "stroke_color", "shadow_color")
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        return _clean_hex_color(value)


class OverlayStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    height_ratio: float = Field(default=0.22, ge=0.10, le=0.45)
    background_color: str = "#000000"
    background_opacity: float = Field(default=0.55, ge=0.0, le=1.0)
    border_radius: int = Field(default=32, ge=0, le=120)
    padding_x: int = Field(default=48, ge=0, le=200)
    padding_y: int = Field(default=28, ge=0, le=160)
    accent_color: str | None = None
    show_accent_bar: bool = False
    show_soft_gradient: bool = True
    style_type: str = "solid_panel"

    @field_validator("background_color")
    @classmethod
    def validate_background_color(cls, value: str) -> str:
        return _clean_hex_color(value)

    @field_validator("accent_color")
    @classmethod
    def validate_accent_color(cls, value: str | None) -> str | None:
        return _clean_hex_color(value) if value else None


class VisualStylePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subtitle: SubtitleStyle
    overlay: OverlayStyle
    recommended_for: list[str] = Field(default_factory=list)


class VisualStyleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset_id: str = "clean_review_light"
    custom_overrides: dict[str, Any] | None = None
    overlay_mode: str = "preset"
    custom_overlay_path: str | None = None
    custom_overlay_height_percent: int | None = Field(default=100, ge=5, le=100)
    custom_overlay_fit_mode: str = "cover"

    @field_validator("preset_id")
    @classmethod
    def clean_preset_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("visual_style.preset_id không được để trống.")
        return cleaned

    @field_validator("overlay_mode")
    @classmethod
    def clean_overlay_mode(cls, value: str) -> str:
        cleaned = value.strip().lower().replace("-", "_")
        allowed = {"preset", "none", "custom"}
        if cleaned not in allowed:
            raise ValueError("visual_style.overlay_mode phải là preset, none hoặc custom.")
        return cleaned

    @field_validator("custom_overlay_fit_mode")
    @classmethod
    def clean_custom_overlay_fit_mode(cls, value: str) -> str:
        cleaned = value.strip().lower().replace("-", "_")
        allowed = {"cover", "contain", "stretch"}
        if cleaned not in allowed:
            raise ValueError("visual_style.custom_overlay_fit_mode phải là cover, contain hoặc stretch.")
        return cleaned

    @field_validator("custom_overlay_path")
    @classmethod
    def clean_custom_overlay_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def _clean_hex_color(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith("#"):
        cleaned = f"#{cleaned}"
    if len(cleaned) != 7:
        raise ValueError(f"Màu phải dùng định dạng #RRGGBB: {value}")
    try:
        int(cleaned[1:], 16)
    except ValueError as exc:
        raise ValueError(f"Màu phải dùng định dạng #RRGGBB: {value}") from exc
    return cleaned.upper()
