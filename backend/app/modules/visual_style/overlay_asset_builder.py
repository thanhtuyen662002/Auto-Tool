from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.modules.visual_style.style_schema import VisualStylePreset
from app.modules.visual_style.subtitle_style_renderer import wrap_subtitle_text
from app.utils.file_utils import ensure_dir


def build_overlay_asset(
    preset: VisualStylePreset,
    width: int,
    height: int,
    output_path: str,
) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if not preset.overlay.enabled:
        image.save(target)
        return str(target)

    overlay = preset.overlay
    panel_height = _panel_height(height, overlay.height_ratio)
    panel_margin_x = max(16, min(width // 10, overlay.padding_x // 2))
    panel_margin_bottom = max(18, min(height // 24, overlay.padding_y // 2))
    panel_x0 = panel_margin_x
    panel_y0 = height - panel_height - panel_margin_bottom
    panel_x1 = width - panel_margin_x
    panel_y1 = height - panel_margin_bottom
    alpha = _alpha(overlay.background_opacity)
    fill = (*_hex_to_rgb(overlay.background_color), alpha)

    panel = Image.new("RGBA", (panel_x1 - panel_x0, panel_y1 - panel_y0), (0, 0, 0, 0))
    mask = Image.new("L", panel.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = min(overlay.border_radius, panel.size[0] // 2, panel.size[1] // 2)
    mask_draw.rounded_rectangle((0, 0, panel.size[0] - 1, panel.size[1] - 1), radius=radius, fill=255)

    if overlay.show_soft_gradient:
        panel = _gradient_panel(panel.size, fill)
    else:
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((0, 0, panel.size[0] - 1, panel.size[1] - 1), radius=radius, fill=fill)

    image.alpha_composite(Image.composite(panel, Image.new("RGBA", panel.size, (0, 0, 0, 0)), mask), (panel_x0, panel_y0))

    if overlay.show_accent_bar and overlay.accent_color:
        draw = ImageDraw.Draw(image)
        accent_width = max(8, width // 120)
        accent_radius = max(4, accent_width // 2)
        accent_x0 = panel_x0 + max(18, overlay.padding_x // 3)
        accent_y0 = panel_y0 + max(18, overlay.padding_y // 2)
        accent_y1 = panel_y1 - max(18, overlay.padding_y // 2)
        accent_fill = (*_hex_to_rgb(overlay.accent_color), min(255, alpha + 30))
        draw.rounded_rectangle(
            (accent_x0, accent_y0, accent_x0 + accent_width, accent_y1),
            radius=accent_radius,
            fill=accent_fill,
        )

    image.save(target)
    return str(target)


def build_style_preview_image(
    preset: VisualStylePreset,
    sample_text: str,
    width: int,
    height: int,
    output_path: str,
) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    image = Image.new("RGBA", (width, height), (232, 236, 242, 255))
    draw = ImageDraw.Draw(image)

    grid_color = (206, 214, 224, 255)
    for y in range(0, height, max(80, height // 18)):
        draw.line((0, y, width, y), fill=grid_color, width=1)
    for x in range(0, width, max(80, width // 10)):
        draw.line((x, 0, x, height), fill=grid_color, width=1)

    product_box = (
        int(width * 0.22),
        int(height * 0.18),
        int(width * 0.78),
        int(height * 0.62),
    )
    draw.rounded_rectangle(product_box, radius=36, fill=(255, 255, 255, 230), outline=(180, 190, 205, 255), width=3)
    draw.text((product_box[0] + 36, product_box[1] + 36), "Sample Product", fill=(70, 80, 95, 255))

    overlay_path = target.with_name(f"{target.stem}_overlay.png")
    build_overlay_asset(preset, width, height, str(overlay_path))
    overlay = Image.open(overlay_path).convert("RGBA")
    image.alpha_composite(overlay)

    _draw_sample_subtitle(image, preset, sample_text)
    image.convert("RGB").save(target)
    return str(target)


def _draw_sample_subtitle(image: Image.Image, preset: VisualStylePreset, sample_text: str) -> None:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    subtitle = preset.subtitle
    overlay = preset.overlay
    panel_height = _panel_height(height, overlay.height_ratio)
    panel_top = height - panel_height - max(18, min(height // 24, overlay.padding_y // 2))
    panel_center_y = panel_top + panel_height // 2
    font_size = max(24, min(96, subtitle.font_size))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    lines = wrap_subtitle_text(sample_text, subtitle.max_chars_per_line, subtitle.max_lines)
    line_spacing = int(font_size * 0.28)
    bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [bbox[3] - bbox[1] for bbox in bboxes]
    block_height = sum(line_heights) + max(0, len(lines) - 1) * line_spacing
    y = panel_center_y - block_height // 2
    color = (*_hex_to_rgb(subtitle.font_color), 255)
    stroke_color = (*_hex_to_rgb(subtitle.stroke_color), 255)
    for line, bbox, line_height in zip(lines, bboxes, line_heights):
        text_width = bbox[2] - bbox[0]
        draw.text(
            ((width - text_width) // 2, y),
            line,
            fill=color,
            font=font,
            stroke_width=subtitle.stroke_width,
            stroke_fill=stroke_color,
        )
        y += line_height + line_spacing


def _gradient_panel(size: tuple[int, int], fill: tuple[int, int, int, int]) -> Image.Image:
    width, height = size
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    base_r, base_g, base_b, base_alpha = fill
    for y in range(height):
        factor = 1.0 - (y / max(1, height - 1)) * 0.18
        alpha = int(base_alpha * factor)
        ImageDraw.Draw(panel).line((0, y, width, y), fill=(base_r, base_g, base_b, alpha))
    return panel


def _panel_height(height: int, ratio: float) -> int:
    return max(120, int(height * max(0.10, min(0.45, ratio))))


def _alpha(opacity: float) -> int:
    return int(max(0.0, min(1.0, opacity)) * 255)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    cleaned = hex_color.strip().lstrip("#")
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)

