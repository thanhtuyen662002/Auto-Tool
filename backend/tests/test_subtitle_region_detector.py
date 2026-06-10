from __future__ import annotations

from app.modules.hardsub_ocr.subtitle_region_detector import SubtitleRegionDetector


def test_bottom_auto_region_uses_lower_video_area():
    region = SubtitleRegionDetector().detect_region(1080, 1920, mode="bottom_auto")

    assert region.x == 0
    assert region.y == 1056
    assert region.width == 1080
    assert region.height == 672


def test_manual_region_is_clamped_to_frame():
    region = SubtitleRegionDetector().detect_region(
        1080,
        1920,
        mode="manual",
        manual_region={"x": 1000, "y": 1800, "width": 300, "height": 500},
    )

    assert region.x == 1000
    assert region.y == 1800
    assert region.width == 80
    assert region.height == 120
