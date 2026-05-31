from __future__ import annotations

from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.segment_scoring.segment_scorer import SegmentScorer, build_scoring_report
from app.modules.timeline_builder.timeline_builder import TimelineBuilder
from app.schemas.media_schema import VideoSegment


class EmptySampler:
    def sample_frames(self, video_path: str, start: float, end: float, max_frames: int = 5):
        return []


def _segment(source_path: str, score: float = 0.5) -> VideoSegment:
    return VideoSegment(
        id="",
        source_path=source_path,
        start=0,
        end=2,
        duration=2,
        score=score,
    )


def _score(segment: VideoSegment, score: float, rejected: bool = False) -> SegmentScore:
    return SegmentScore(
        segment_id=segment.id or source_id(segment.source_path),
        source_path=segment.source_path,
        start=segment.start,
        end=segment.end,
        duration=segment.duration,
        brightness_score=score,
        sharpness_score=score,
        motion_score=score,
        freeze_score=score,
        stability_score=score,
        overall_score=score,
        is_rejected=rejected,
        reject_reasons=["low_quality_segment"] if rejected else [],
        tags=["sharp"] if score > 0.75 else [],
    )


def test_scorer_rejects_segment_when_frames_are_empty():
    segment = _segment("missing.mp4")
    scorer = SegmentScorer(sampler=EmptySampler())

    result = scorer.score_segment(segment)

    assert result.is_rejected is True
    assert "no_frames" in result.reject_reasons
    assert result.overall_score == 0


def test_score_segments_does_not_crash_on_empty_frames():
    segment = _segment("missing.mp4")
    scorer = SegmentScorer(sampler=EmptySampler())

    [scored] = scorer.score_segments([segment])

    assert scored.score_detail is not None
    assert scored.score_detail.is_rejected is True
    assert scored.score == 0


def test_scoring_report_counts_rejection_reasons():
    good = _segment("good.mp4", score=0.9)
    bad = _segment("bad.mp4", score=0.1)
    good = good.model_copy(update={"id": source_id("good.mp4"), "score_detail": _score(good, 0.9), "score": 0.9})
    bad = bad.model_copy(update={"id": source_id("bad.mp4"), "score_detail": _score(bad, 0.1, True), "score": 0.1})

    report = build_scoring_report([good, bad])

    assert report["total_segments"] == 2
    assert report["usable_segments"] == 1
    assert report["rejected_segments"] == 1
    assert report["rejection_summary"]["low_quality_segment"] == 1


def test_weighted_timeline_prefers_high_score_segments():
    high = _segment("high.mp4", score=1.0)
    low = _segment("low.mp4", score=0.1)
    high = high.model_copy(update={"id": "high", "score_detail": _score(high, 1.0), "score": 1.0})
    low = low.model_copy(update={"id": "low", "score_detail": _score(low, 0.1), "score": 0.1})

    timelines = TimelineBuilder().build_timelines(
        segments=[high, low],
        output_count=80,
        target_duration=1,
        speed_variation=0,
    )
    high_count = sum(1 for timeline in timelines if timeline.clips[0].source_path == "high.mp4")

    assert high_count >= 60


def source_id(value: str) -> str:
    return value.replace(".", "-")
