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


def test_wrap_subtitle_text_preserves_all_lines() -> None:
    lines = wrap_subtitle_text(
        "Đây là một câu subtitle dài cần được xuống dòng hợp lý",
        max_chars_per_line=18,
        max_lines=2,
    )

    assert len(lines) > 2
    assert " ".join(lines) == "Đây là một câu subtitle dài cần được xuống dòng hợp lý"


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


def test_generate_ass_subtitle_splits_long_lines_without_dropping_text(tmp_path) -> None:
    preset = get_visual_style_preset("sale_bold_red")
    output_path = tmp_path / "video_001_sub.ass"
    text = "Một câu rất dài có nhiều thông tin quan trọng không được phép bị cắt mất khi render subtitle"

    generate_ass_subtitle(
        [{"start_hint": 0, "end_hint": 4, "text": text}],
        preset,
        1080,
        1920,
        str(output_path),
    )

    content = output_path.read_text(encoding="utf-8").replace(r"\N", " ")

    assert content.count("Dialogue: 0,") > 1
    for phrase in ["Một câu rất dài", "thông", "tin", "quan", "trọng", "render subtitle"]:
        assert phrase in content


def test_generate_ass_subtitle_can_draw_cover_background(tmp_path) -> None:
    preset = get_visual_style_preset("clean_review_light")
    output_path = tmp_path / "video_001_cover.ass"

    generate_ass_subtitle(
        [{"start_hint": 0, "end_hint": 2, "text": "Chỉ còn phụ đề Việt"}],
        preset,
        1080,
        1920,
        str(output_path),
        cover_background_enabled=True,
        cover_background_height_ratio=0.22,
        cover_background_opacity=0.9,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "Style: SubtitleCover," in content
    assert "Dialogue: 0,0:00:00.00,0:00:02.00,SubtitleCover" in content
    assert r"{\p1\pos(0,0)}m 0 " in content
    assert "Dialogue: 1,0:00:00.00,0:00:02.00,Default" in content


def test_generate_ass_subtitle_uses_custom_shadow_size(tmp_path) -> None:
    preset = get_visual_style_preset("clean_review_light")
    preset = preset.model_copy(
        update={"subtitle": preset.subtitle.model_copy(update={"shadow_enabled": True, "shadow_size": 6})}
    )
    output_path = tmp_path / "video_001_shadow.ass"

    generate_ass_subtitle(
        [{"start_hint": 0, "end_hint": 2, "text": "Bóng chữ lớn hơn"}],
        preset,
        1080,
        1920,
        str(output_path),
    )

    content = output_path.read_text(encoding="utf-8")

    assert ",2,6,5," in content


def test_generate_ass_subtitle_uses_timed_cover_segments(tmp_path) -> None:
    preset = get_visual_style_preset("clean_review_light")
    output_path = tmp_path / "video_001_dynamic_cover.ass"

    generate_ass_subtitle(
        [{"start_hint": 0, "end_hint": 2, "text": "Phá»¥ Ä‘á» Viá»‡t báº¡m theo chá»¯ Trung"}],
        preset,
        1080,
        1920,
        str(output_path),
        cover_background_enabled=True,
        cover_background_height_ratio=0.22,
        cover_background_segments=[
            {
                "start": 0.0,
                "end": 1.0,
                "left_ratio": 0.1,
                "top_ratio": 0.72,
                "right_ratio": 0.9,
                "bottom_edge_ratio": 0.78,
            },
            {
                "start": 1.0,
                "end": 2.0,
                "left_ratio": 0.15,
                "top_ratio": 0.66,
                "right_ratio": 0.85,
                "bottom_edge_ratio": 0.72,
            },
        ],
    )

    content = output_path.read_text(encoding="utf-8")

    assert "Dialogue: 0,0:00:00.00,0:00:01.00,SubtitleCover" in content
    assert "Dialogue: 0,0:00:01.00,0:00:02.00,SubtitleCover" in content
    assert r"m 108 1382 l 972 1382 l 972 1498 l 108 1498" in content
    assert r"m 162 1267 l 918 1267 l 918 1382 l 162 1382" in content
    assert r"\pos(540,1440)" in content
