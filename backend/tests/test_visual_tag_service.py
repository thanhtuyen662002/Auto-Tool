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
