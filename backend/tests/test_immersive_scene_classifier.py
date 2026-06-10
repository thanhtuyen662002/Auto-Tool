from __future__ import annotations

from app.modules.silent_immersive_reup.immersive_scene_classifier import ImmersiveSceneClassifier
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


def test_scene_classifier_uses_timeline_and_motion():
    segments = [
        SilentVisualSegment(id="a", video_path="clip.mp4", start=0, end=2, duration=2, motion_score=0.1, sharpness_score=0.5),
        SilentVisualSegment(id="b", video_path="clip.mp4", start=2, end=4, duration=2, motion_score=0.8, sharpness_score=0.4),
        SilentVisualSegment(id="c", video_path="clip.mp4", start=4, end=6, duration=2, motion_score=0.1, sharpness_score=0.7),
    ]

    result = ImmersiveSceneClassifier().classify_segments(segments)

    assert result[0].segment_type == VisualSegmentType.product_reveal
    assert result[1].segment_type == VisualSegmentType.demo
    assert result[2].segment_type in {VisualSegmentType.result, VisualSegmentType.closeup}
