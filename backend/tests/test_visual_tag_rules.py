from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType
from app.modules.silent_visual_tagging.visual_tag_rules import VisualTagRules


def test_unboxing_segment_maps_to_unboxing_and_packaging():
    segment = SilentVisualSegment(
        id="seg_1",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.unboxing,
    )
    names = {tag.tag for tag in VisualTagRules().tags_from_segment_features(segment, 0, 3)}
    assert {"unboxing", "packaging", "first_look"} <= names


def test_high_motion_segment_maps_to_usage_demo():
    segment = SilentVisualSegment(
        id="seg_2",
        video_path="clip.mp4",
        start=2,
        end=4,
        duration=2,
        motion_score=0.8,
        sharpness_score=0.7,
    )
    names = {tag.tag for tag in VisualTagRules().tags_from_segment_features(segment, 1, 4)}
    assert {"usage_demo", "hands_operation", "high_motion"} <= names


def test_two_segment_video_only_marks_last_segment_as_final():
    rules = VisualTagRules()
    first = SilentVisualSegment(
        id="seg_1",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.product_reveal,
    )
    last = first.model_copy(update={"id": "seg_2", "start": 2, "end": 4})

    first_tags = {tag.tag for tag in rules.tags_from_segment_features(first, 0, 2)}
    last_tags = {tag.tag for tag in rules.tags_from_segment_features(last, 1, 2)}

    assert "cta_scene" not in first_tags
    assert "final_result" not in first_tags
    assert "cta_scene" in last_tags
    assert "final_result" in last_tags
