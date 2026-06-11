from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


def _segments() -> list[SilentVisualSegment]:
    types = [VisualSegmentType.product_reveal, VisualSegmentType.closeup, VisualSegmentType.demo, VisualSegmentType.result]
    return [
        SilentVisualSegment(id=f"seg_{index}", video_path="clip.mp4", start=index * 2, end=(index + 1) * 2, duration=2, segment_type=kind)
        for index, kind in enumerate(types)
    ]


def test_generator_uses_kitchen_templates_adds_cta_and_quality_scores():
    captions = ImmersiveCaptionGenerator().generate_captions(
        "clip.mp4",
        _segments(),
        "chill_immersive",
        product_context={"industry": "kitchen_goods"},
        industry="kitchen_goods",
    )
    assert len(captions) == 4
    assert captions[-1].template_id and ".cta." in captions[-1].template_id
    assert any("bếp" in caption.text.casefold() for caption in captions)
    assert all(caption.quality_score is not None for caption in captions)
    assert all(len(caption.text) <= 56 for caption in captions)


def test_generator_uses_desk_setup_language():
    captions = ImmersiveCaptionGenerator().generate_captions(
        "clip.mp4",
        _segments(),
        "chill_immersive",
        product_context={"industry": "desk_setup"},
        industry="desk_setup",
    )
    assert any(any(word in caption.text.casefold() for word in ("bàn", "setup", "làm việc")) for caption in captions)
