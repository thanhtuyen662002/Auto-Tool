from __future__ import annotations

from PIL import Image

from app.modules.visual_style.overlay_asset_builder import build_overlay_asset, build_style_preview_image
from app.modules.visual_style.style_registry import get_visual_style_preset


def test_overlay_asset_builder_creates_transparent_png_with_visible_panel(tmp_path) -> None:
    preset = get_visual_style_preset("tech_dark_neon")
    output_path = tmp_path / "overlay.png"

    result = build_overlay_asset(preset, 360, 640, str(output_path))

    assert result == str(output_path)
    assert output_path.exists()
    image = Image.open(output_path).convert("RGBA")
    assert image.size == (360, 640)
    alpha_bbox = image.getchannel("A").getbbox()
    assert alpha_bbox is not None
    assert alpha_bbox[1] > 0
    assert image.getpixel((10, 10))[3] == 0


def test_style_preview_image_contains_flattened_preview(tmp_path) -> None:
    preset = get_visual_style_preset("clean_review_light")
    output_path = tmp_path / "preview.png"

    build_style_preview_image(preset, "Một câu subtitle dễ đọc", 360, 640, str(output_path))

    assert output_path.exists()
    image = Image.open(output_path)
    assert image.mode == "RGB"
    assert image.size == (360, 640)
