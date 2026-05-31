from __future__ import annotations

from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.timeline_templates.product_timeline_builder import (
    ProductTimelineBuilder,
    select_segment_for_slot,
)
from app.modules.timeline_templates.template_registry import DEFAULT_TEMPLATE_ID, get_timeline_template
from app.schemas.media_schema import VideoSegment


def test_builder_creates_timeline_near_target_duration():
    segments = [
        _segment("a.mp4", 0, 8, 0.9, ["sharp", "stable", "bright"]),
        _segment("b.mp4", 0, 8, 0.8, ["high_motion", "stable"]),
        _segment("c.mp4", 0, 8, 0.75, ["bright", "stable"]),
    ]

    [timeline] = ProductTimelineBuilder().build_timelines(
        segments=segments,
        output_count=1,
        target_duration=12,
        template_id="ugc_reviewer_natural",
        speed_variation=0,
    )

    assert abs(sum(clip.duration for clip in timeline.clips) - 12) <= 0.05
    assert timeline.template_id == "ugc_reviewer_natural"


def test_builder_prefers_high_score_segments():
    segments = [
        _segment("high.mp4", 0, 4, 1.0, ["sharp", "stable", "bright", "high_motion"]),
        _segment("low.mp4", 0, 4, 0.1, []),
    ]

    timelines = ProductTimelineBuilder().build_timelines(
        segments=segments,
        output_count=40,
        target_duration=2,
        template_id="product_showcase_clean",
        speed_variation=0,
    )
    first_clip_high_count = sum(
        1
        for timeline in timelines
        if timeline.clips[0].source_path == "high.mp4"
    )

    assert first_clip_high_count >= 30


def test_select_segment_prefers_matching_tags_over_many_seeds():
    template = get_timeline_template("product_showcase_clean")
    slot = template.slots[1]
    matching = _segment("matching.mp4", 0, 4, 0.9, ["sharp", "stable", "bright"])
    plain = _segment("plain.mp4", 0, 4, 0.9, [])

    matching_count = sum(
        1
        for seed in range(100)
        if select_segment_for_slot([matching, plain], slot, [], seed).source_path == "matching.mp4"
    )

    assert matching_count >= 60


def test_builder_avoids_using_one_source_three_times_when_alternatives_exist():
    segments = [
        _segment("a.mp4", 0, 8, 0.9, ["sharp", "stable", "bright"]),
        _segment("b.mp4", 0, 8, 0.85, ["high_motion", "stable"]),
        _segment("c.mp4", 0, 8, 0.8, ["bright", "stable"]),
    ]

    [timeline] = ProductTimelineBuilder().build_timelines(
        segments=segments,
        output_count=1,
        target_duration=20,
        template_id="ugc_reviewer_natural",
        speed_variation=0,
    )
    sources = [clip.source_path for clip in timeline.clips]

    for first, second, third in zip(sources, sources[1:], sources[2:]):
        assert len({first, second, third}) > 1


def test_builder_falls_back_when_tags_are_missing_and_adds_metadata():
    segments = [
        _segment("a.mp4", 0, 6, 0.7, []),
        _segment("b.mp4", 0, 6, 0.6, []),
    ]

    [timeline] = ProductTimelineBuilder().build_timelines(
        segments=segments,
        output_count=1,
        target_duration=8,
        template_id="missing_template",
        speed_variation=0,
    )

    assert timeline.template_id == DEFAULT_TEMPLATE_ID
    assert timeline.clips
    assert all(clip.slot_name for clip in timeline.clips)
    assert all(clip.text_role for clip in timeline.clips)
    assert all(clip.segment_score is not None for clip in timeline.clips)


def test_builder_does_not_repeat_same_segment_when_enough_segments_exist():
    segments = [
        _segment("a.mp4", 0, 3, 0.95, ["sharp", "stable", "bright"]),
        _segment("b.mp4", 0, 3, 0.9, ["high_motion", "stable"]),
        _segment("c.mp4", 0, 3, 0.85, ["bright", "stable"]),
        _segment("d.mp4", 0, 3, 0.8, ["sharp", "bright"]),
        _segment("e.mp4", 0, 3, 0.75, ["stable"]),
        _segment("f.mp4", 0, 3, 0.7, ["high_motion"]),
    ]

    [timeline] = ProductTimelineBuilder().build_timelines(
        segments=segments,
        output_count=1,
        target_duration=10,
        template_id="ugc_reviewer_natural",
        speed_variation=0,
    )
    segment_ids = [clip.segment_id for clip in timeline.clips]

    assert len(segment_ids) == len(set(segment_ids))


def test_select_segment_avoids_used_segment_when_alternative_exists():
    template = get_timeline_template("product_showcase_clean")
    slot = template.slots[0]
    used = _segment("used.mp4", 0, 3, 1.0, ["sharp", "bright", "high_motion"])
    fresh = _segment("fresh.mp4", 0, 3, 0.6, ["sharp", "bright", "high_motion"])

    selected = select_segment_for_slot(
        [used, fresh],
        slot,
        used_sources=[],
        used_segment_ids={used.id},
        random_seed=1,
    )

    assert selected.id == fresh.id


def test_select_segment_avoids_recent_source_when_alternative_exists():
    template = get_timeline_template("ugc_reviewer_natural")
    slot = template.slots[2]
    recent = _segment("recent.mp4", 0, 3, 1.0, ["high_motion"])
    alternative = _segment("alternative.mp4", 0, 3, 0.8, ["high_motion"])

    selected = select_segment_for_slot(
        [recent, alternative],
        slot,
        used_sources=["older.mp4", "recent.mp4"],
        used_segment_ids=set(),
        random_seed=1,
    )

    assert selected.source_path == "alternative.mp4"


def _segment(source_path: str, start: float, end: float, score: float, tags: list[str]) -> VideoSegment:
    duration = end - start
    segment = VideoSegment(
        id=source_path,
        source_path=source_path,
        start=start,
        end=end,
        duration=duration,
        score=score,
        tags=tags,
    )
    return segment.model_copy(
        update={
            "score_detail": SegmentScore(
                segment_id=source_path,
                source_path=source_path,
                start=start,
                end=end,
                duration=duration,
                brightness_score=score,
                sharpness_score=score,
                motion_score=score,
                freeze_score=score,
                stability_score=score,
                overall_score=score,
                is_rejected=False,
                reject_reasons=[],
                tags=tags,
            )
        }
    )
