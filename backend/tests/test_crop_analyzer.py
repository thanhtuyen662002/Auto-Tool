from __future__ import annotations

from app.modules.crop_safety import crop_analyzer
from app.modules.crop_safety.crop_analyzer import CropAnalyzer
from app.schemas.media_schema import MediaFile


class FakeFrameSampler:
    def sample_frames(self, source_path: str, start: float, end: float, max_frames: int = 3):
        return [object()]


class FakeSaliencyAnalyzer:
    def __init__(self, result: dict) -> None:
        self.result = result

    def analyze_frame(self, frame):
        return self.result


def _media(width: int, height: int) -> MediaFile:
    return MediaFile(
        path="source.mp4",
        duration=8.0,
        width=width,
        height=height,
        fps=30,
        has_audio=True,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    )


def _saliency(**overrides) -> dict:
    base = {
        "center_x": 0.5,
        "center_y": 0.5,
        "left_edge_score": 0.12,
        "right_edge_score": 0.12,
        "bottom_score": 0.12,
        "center_score": 0.50,
        "total_score": 0.25,
    }
    base.update(overrides)
    return base


def test_crop_analyzer_uses_blur_background_when_landscape_content_is_near_edge(monkeypatch) -> None:
    monkeypatch.setattr(crop_analyzer, "probe_video", lambda path: _media(1920, 1080))
    analyzer = CropAnalyzer(
        frame_sampler=FakeFrameSampler(),
        saliency_analyzer=FakeSaliencyAnalyzer(
            _saliency(center_x=0.12, left_edge_score=0.62, right_edge_score=0.20, bottom_score=0.42)
        ),
    )

    result = analyzer.analyze_video_or_segment(
        source_path="source.mp4",
        start=0,
        end=4,
        target_width=1080,
        target_height=1920,
        overlay_height_ratio=0.33,
        zoom_motion=50,
    )

    assert result.crop_mode == "safe_fit_blur_background"
    assert result.fallback_used is True
    assert "important_content_near_edge" in result.warnings
    assert result.effective_zoom_motion == 15


def test_crop_analyzer_keeps_matching_portrait_aspect_without_crop(monkeypatch) -> None:
    monkeypatch.setattr(crop_analyzer, "probe_video", lambda path: _media(1080, 1920))
    analyzer = CropAnalyzer(
        frame_sampler=FakeFrameSampler(),
        saliency_analyzer=FakeSaliencyAnalyzer(_saliency()),
    )

    result = analyzer.analyze_video_or_segment(
        source_path="source.mp4",
        start=0,
        end=4,
        target_width=1080,
        target_height=1920,
        overlay_height_ratio=0.22,
        zoom_motion=0,
    )

    assert result.crop_mode == "no_crop_scale"
    assert result.recommended_crop.width == 1080
    assert result.recommended_crop.height == 1920
    assert result.overall_safety_score >= 0.85
