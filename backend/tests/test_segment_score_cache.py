from __future__ import annotations

from app.modules.cache.cache_service import CacheService
from app.modules.segment_scoring.segment_scorer import SegmentScorer
from app.schemas.media_schema import VideoSegment


class CountingSampler:
    def __init__(self) -> None:
        self.calls = 0

    def sample_frames(self, video_path: str, start: float, end: float, max_frames: int = 5):
        self.calls += 1
        return [object(), object()]


class StaticAnalyzer:
    def analyze_frames(self, frames):
        return {
            "brightness_score": 0.8,
            "sharpness_score": 0.8,
            "motion_score": 0.7,
            "freeze_score": 0.9,
            "stability_score": 0.8,
        }


def test_segment_scoring_uses_cache_on_second_run(tmp_path) -> None:
    segment = VideoSegment(
        source_path=str(tmp_path / "source.mp4"),
        start=0.5,
        end=2.5,
        duration=2.0,
        score=0.5,
    )
    cache_service = CacheService(tmp_path / ".cache")
    sampler = CountingSampler()

    first = SegmentScorer(
        sampler=sampler,
        analyzer=StaticAnalyzer(),
        cache_service=cache_service,
        settings_hash="test-settings",
    ).score_segment(segment)
    second = SegmentScorer(
        sampler=sampler,
        analyzer=StaticAnalyzer(),
        cache_service=cache_service,
        settings_hash="test-settings",
    ).score_segment(segment)

    assert sampler.calls == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.overall_score == first.overall_score
