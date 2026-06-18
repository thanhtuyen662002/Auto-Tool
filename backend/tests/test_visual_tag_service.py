from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType
from app.modules.silent_visual_tagging.visual_tag_service import VisualTagService


def test_service_recommends_industry_from_multiple_segments():
    segments = [
        SilentVisualSegment(
            id=f"seg_{index}",
            video_path="kitchen/clip.mp4",
            start=index * 2,
            end=(index + 1) * 2,
            duration=2,
            segment_type=VisualSegmentType.demo,
            ocr_text="厨房 使用",
            motion_score=0.7,
        )
        for index in range(3)
    ]
    report = VisualTagService().tag_video_segments(
        "kitchen/clip.mp4",
        segments,
        product_context={"industry": "kitchen_goods"},
    )
    assert report.recommended_industry == "kitchen_goods"
    assert report.average_confidence > 0.5
    assert all(result.primary_industry == "kitchen_goods" for result in report.segment_results)


def test_placeholder_product_context_does_not_block_filename_tags():
    segments = [
        SilentVisualSegment(
            id="seg_001",
            video_path="source/clip.mp4",
            start=0,
            end=2,
            duration=2,
            segment_type=VisualSegmentType.product_reveal,
        )
    ]

    report = VisualTagService().tag_video_segments(
        "source/clip.mp4",
        segments,
        product_context={
            "product_name": "Douyin Reup",
            "name": "Douyin Reup",
            "features": ["D\u1ecbch subtitle", "Th\u00eam overlay"],
            "product_context_lock_enabled": True,
        },
        filename="#\u6536\u7eb3\u6574\u7406 #\u7f6e\u7269\u67b6",
    )

    assert report.recommended_industry == "storage_organization"
    assert any(tag.source == "filename" for tag in report.video_level_tags)
