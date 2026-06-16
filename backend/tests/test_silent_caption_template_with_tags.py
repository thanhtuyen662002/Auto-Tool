from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


def test_caption_generator_prioritizes_segment_primary_industry_and_action():
    segment = SilentVisualSegment(
        id="seg_1",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.unknown,
        primary_industry="kitchen_goods",
        primary_action="usage_demo",
    )
    caption = ImmersiveCaptionGenerator().generate_captions(
        "clip.mp4",
        [segment],
        "chill_immersive",
        industry="desk_setup",
        use_visual_tags=True,
    )[0]
    assert caption.selected_industry == "kitchen_goods"
    assert caption.selected_intent == "demo"
    assert "kitchen_goods + demo" in (caption.selection_reason or "")


def test_caption_generator_trusts_product_context_over_visual_tag_industry():
    segment = SilentVisualSegment(
        id="seg_1",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.unknown,
        primary_industry="cleaning_goods",
        primary_action="usage_demo",
    )

    caption = ImmersiveCaptionGenerator().generate_captions(
        "clip.mp4",
        [segment],
        "chill_immersive",
        product_context={"industry": "kitchen_goods", "product_name": "Nồi nấu ăn"},
        use_visual_tags=True,
    )[0]

    assert caption.selected_industry == "kitchen_goods"
    assert caption.selected_intent == "demo"
