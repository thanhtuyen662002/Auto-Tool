from __future__ import annotations

from app.modules.crop_safety.crop_schema import CropBox
from app.modules.crop_safety.crop_strategy import build_crop_video_filter


def test_crop_filter_builder_creates_safe_fit_blur_background_graph() -> None:
    filtergraph = build_crop_video_filter(
        crop_mode="safe_fit_blur_background",
        crop_box=None,
        target_width=1080,
        target_height=1920,
        fps=30,
        speed=1.0,
        grain=0,
    )

    assert "[0:v]" in filtergraph
    assert "boxblur=20:1[bg]" in filtergraph
    assert "overlay=(W-w)/2:(H-h)/2" in filtergraph
    assert "scale=1080:1920:force_original_aspect_ratio=decrease[fg]" in filtergraph


def test_crop_filter_builder_uses_recommended_crop_box_for_smart_center() -> None:
    filtergraph = build_crop_video_filter(
        crop_mode="smart_center",
        crop_box=CropBox(x=240, y=0, width=608, height=1080),
        target_width=1080,
        target_height=1920,
        fps=30,
        speed=1.05,
        grain=12,
    )

    assert "crop=608:1080:240:0" in filtergraph
    assert "scale=1080:1920" in filtergraph
    assert "setpts=PTS/1.050000" in filtergraph
    assert "noise=alls=12:allf=t+u" in filtergraph
