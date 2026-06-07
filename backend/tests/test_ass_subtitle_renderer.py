from __future__ import annotations

from app.modules.visual_style.style_registry import get_visual_style_preset
from app.modules.visual_style.subtitle_style_renderer import (
    generate_ass_subtitle,
    hex_to_ass_color,
    wrap_subtitle_text,
)


def test_hex_to_ass_color_converts_rgb_to_ass_bgr() -> None:
    assert hex_to_ass_color("#112233") == "&H00332211"
    assert hex_to_ass_color("#FFFFFF", alpha=0.5) == "&H80FFFFFF"


def test_wrap_subtitle_text_respects_max_lines() -> None:
    lines = wrap_subtitle_text(
        "Đây là một câu subtitle dài cần được xuống dòng hợp lý",
        max_chars_per_line=18,
        max_lines=2,
    )

    assert len(lines) <= 2
    assert all(len(line) <= 18 for line in lines)


def test_generate_ass_subtitle_writes_positioned_ass_file(tmp_path) -> None:
    preset = get_visual_style_preset("sale_bold_red")
    output_path = tmp_path / "video_001_sub.ass"

    generate_ass_subtitle(
        [
            {"start_hint": 0, "end_hint": 2.8, "text": "Sản phẩm này rất đáng xem"},
            {"start_hint": 2.8, "end_hint": 5.5, "text": "Nhỏ gọn, dễ dùng mỗi ngày"},
        ],
        preset,
        1080,
        1920,
        str(output_path),
    )

    content = output_path.read_text(encoding="utf-8")
    assert "[V4+ Styles]" in content
    assert "Style: Default," in content
    assert r"\pos(540," in content
    assert "Dialogue: 0,0:00:00.00,0:00:02.80" in content
