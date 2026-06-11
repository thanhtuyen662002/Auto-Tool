from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


def test_captions_do_not_repeat_within_video_or_next_batch_item():
    segments = [
        SilentVisualSegment(id=f"seg_{index}", video_path="clip.mp4", start=index * 2, end=(index + 1) * 2, duration=2, segment_type=VisualSegmentType.demo)
        for index in range(16)
    ]
    generator = ImmersiveCaptionGenerator()
    first = generator.generate_captions("clip.mp4", segments, "chill_immersive", industry="general_product")
    second = generator.generate_captions(
        "clip2.mp4",
        segments,
        "chill_immersive",
        industry="general_product",
        recent_caption_texts=[caption.text for caption in first],
    )
    assert len({caption.text for caption in first}) == len(first)
    assert first[0].text != second[0].text
