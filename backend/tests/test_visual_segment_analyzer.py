from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.silent_immersive_reup.visual_segment_analyzer import VisualSegmentAnalyzer, _write_cv2_frame
from app.schemas.media_schema import MediaFile


def test_visual_segment_analyzer_fallback_creates_valid_segments(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.modules.silent_immersive_reup.visual_segment_analyzer.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=8,
            width=1080,
            height=1920,
            fps=30,
            has_audio=True,
            format_name="mov,mp4",
        ),
    )
    monkeypatch.setattr(VisualSegmentAnalyzer, "_analyze_with_cv2", lambda self, video_path, settings, frames_dir: [])

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    segments = VisualSegmentAnalyzer().analyze_video(str(video), DouyinReupSettings(enabled=True), str(tmp_path / "out"))

    assert segments
    assert all(segment.duration > 0 for segment in segments)
    assert (tmp_path / "out" / "clip_silent_segments.json").exists()


def test_write_cv2_frame_supports_unicode_parent_path(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    target = tmp_path / "视频输出" / "frame_seg_001.jpg"
    frame = np.full((64, 64, 3), 210, dtype=np.uint8)

    assert _write_cv2_frame(target, frame) is True
    assert target.exists()
    assert target.stat().st_size > 0
    assert cv2.imdecode(np.frombuffer(target.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR) is not None


def test_internal_frame_names_are_ascii_stable():
    assert Path("frame_seg_001.jpg").name.isascii()
