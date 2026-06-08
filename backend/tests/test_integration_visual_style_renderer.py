from __future__ import annotations

from pathlib import Path

from app.modules.renderer.overlay_renderer import OverlayRenderer
from app.modules.script_writer.script_writer import SubtitleLine
from app.modules.visual_style.overlay_asset_builder import build_overlay_asset
from app.modules.visual_style.style_schema import VisualStyleSettings
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService


def test_visual_style_generates_overlay_asset_and_ass_subtitle(tmp_path: Path) -> None:
    preset = VisualStyleService().resolve_preset(VisualStyleSettings(preset_id="tech_dark_neon"))
    overlay_path = tmp_path / "overlay.png"
    ass_path = tmp_path / "subtitle.ass"

    build_overlay_asset(preset, width=360, height=640, output_path=str(overlay_path))
    generate_ass_subtitle(
        [SubtitleLine(start_hint=0.0, end_hint=1.2, text="Test subtitle")],
        preset,
        video_width=360,
        video_height=640,
        output_path=str(ass_path),
    )

    assert overlay_path.exists()
    assert overlay_path.stat().st_size > 0
    assert ass_path.exists()
    assert "Test subtitle" in ass_path.read_text(encoding="utf-8")


def test_overlay_renderer_escapes_windows_filter_paths() -> None:
    escaped = OverlayRenderer._escape_filter_path(r"D:\Data\Auto Tool\video_001_sub.ass")

    assert "D\\:" in escaped
    assert "\\" not in escaped.replace("\\:", "")
