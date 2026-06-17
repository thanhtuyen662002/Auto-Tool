from __future__ import annotations

from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


def test_caption_generator_uses_product_context():
    segments = [
        SilentVisualSegment(
            id="seg_001",
            video_path="clip.mp4",
            start=0,
            end=2,
            duration=2,
            segment_type=VisualSegmentType.product_reveal,
            visual_score=0.8,
        )
    ]

    captions = ImmersiveCaptionGenerator().generate_captions(
        video_path="clip.mp4",
        segments=segments,
        strategy="chill_immersive",
        product_context={"product_name": "Kệ bếp gọn", "features": ["tiết kiệm không gian"]},
    )

    assert captions[0].source == "visual_generated"
    assert "Kệ bếp gọn" in captions[0].text
    assert len(captions[0].text) <= 52


def test_caption_generator_without_product_context_uses_generic_caption():
    segment = SilentVisualSegment(
        id="seg_001",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.product_reveal,
    )

    captions = ImmersiveCaptionGenerator().generate_captions(
        video_path="clip.mp4",
        segments=[segment],
        strategy="chill_immersive",
        product_context=None,
    )

    assert captions[0].text
    assert len(captions[0].text) <= 52


def test_caption_generator_without_product_context_does_not_trust_misdetected_industry():
    segment = SilentVisualSegment(
        id="seg_001",
        video_path="clip.mp4",
        start=0,
        end=2,
        duration=2,
        segment_type=VisualSegmentType.demo,
        primary_industry="cleaning_goods",
        primary_action="cleaning",
        visual_tag_confidence=0.95,
    )

    captions = ImmersiveCaptionGenerator().generate_captions(
        video_path="clip.mp4",
        segments=[segment],
        strategy="chill_immersive",
        product_context=None,
        industry="general_product",
        use_visual_tags=True,
    )

    assert captions[0].selected_industry == "general_product"


def test_ocr_caption_has_priority(tmp_path):
    srt = tmp_path / "ocr_vi.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption từ OCR\n", encoding="utf-8")

    captions = ImmersiveCaptionGenerator().generate_captions(
        video_path="clip.mp4",
        segments=[],
        strategy="sales_recut",
        product_context=None,
        ocr_translated_srt_path=str(srt),
    )

    assert captions[0].source == "ocr_translation"
    assert captions[0].text == "Caption từ OCR"
