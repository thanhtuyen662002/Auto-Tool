from __future__ import annotations

import numpy as np

from app.modules.segment_scoring.segment_analyzer import SegmentAnalyzer


def test_dark_frame_has_low_brightness_score():
    analyzer = SegmentAnalyzer()
    frames = [np.zeros((64, 64, 3), dtype=np.uint8) for _ in range(3)]

    result = analyzer.analyze_frames(frames)

    assert result["brightness_score"] < 0.25


def test_overexposed_frame_has_low_brightness_score():
    analyzer = SegmentAnalyzer()
    frames = [np.full((64, 64, 3), 255, dtype=np.uint8) for _ in range(3)]

    result = analyzer.analyze_frames(frames)

    assert result["brightness_score"] < 0.25


def test_sharp_checkerboard_has_high_sharpness_score():
    analyzer = SegmentAnalyzer()
    checker = ((np.indices((64, 64)).sum(axis=0) % 2) * 255).astype(np.uint8)
    frames = [np.dstack([checker, checker, checker]) for _ in range(3)]

    result = analyzer.analyze_frames(frames)

    assert result["sharpness_score"] > 0.75


def test_flat_frame_has_low_sharpness_score():
    analyzer = SegmentAnalyzer()
    frames = [np.full((64, 64, 3), 120, dtype=np.uint8) for _ in range(3)]

    result = analyzer.analyze_frames(frames)

    assert result["sharpness_score"] < 0.25


def test_identical_frames_have_low_freeze_score():
    analyzer = SegmentAnalyzer()
    frame = np.full((64, 64, 3), 120, dtype=np.uint8)

    result = analyzer.analyze_frames([frame.copy() for _ in range(5)])

    assert result["freeze_score"] < 0.30

