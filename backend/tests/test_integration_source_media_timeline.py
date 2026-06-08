from __future__ import annotations

from pathlib import Path

from app import database
from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.source_media_manager.media_filter_service import MediaFilterService
from app.modules.timeline_templates.product_timeline_builder import ProductTimelineBuilder
from app.schemas.media_schema import VideoSegment


def test_source_media_filter_excludes_media_and_prioritizes_favorite_for_timeline(tmp_path: Path) -> None:
    original_db_path = database.DB_PATH
    database.DB_PATH = tmp_path / "source-media-timeline.db"
    database.init_db()

    try:
        source_a = str(tmp_path / "bad_source.mp4")
        source_b = str(tmp_path / "good_source.mp4")
        database.upsert_source_media_review("project-1", source_a, "excluded")
        database.upsert_segment_review("project-1", "b1", source_b, 0.0, 2.0, "favorite")

        segments = [
            _segment("a1", source_a, 0.0, 2.0, 0.98),
            _segment("b1", source_b, 0.0, 2.0, 0.70),
            _segment("b2", source_b, 2.0, 4.0, 0.92),
            _segment("b3", source_b, 4.0, 6.0, 0.88),
        ]

        filtered = MediaFilterService().filter_segments_for_render("project-1", segments)

        assert all(segment.source_path != source_a for segment in filtered)
        assert filtered[0].id == "b1"
        assert filtered[0].user_review_status == "favorite"

        timeline = ProductTimelineBuilder().build_timelines(
            segments=filtered,
            output_count=1,
            target_duration=5.0,
            template_id="product_showcase_clean",
            speed_variation=0,
        )[0]

        assert timeline.clips
        assert all(clip.source_path != source_a for clip in timeline.clips)
        assert any(clip.user_review_status == "favorite" for clip in timeline.clips)
    finally:
        database.DB_PATH = original_db_path


def _segment(segment_id: str, source_path: str, start: float, end: float, score: float) -> VideoSegment:
    return VideoSegment(
        id=segment_id,
        source_path=source_path,
        start=start,
        end=end,
        duration=end - start,
        score=score,
        tags=["product", "bright", "stable"],
        score_detail=SegmentScore(
            segment_id=segment_id,
            source_path=source_path,
            start=start,
            end=end,
            duration=end - start,
            brightness_score=score,
            sharpness_score=score,
            motion_score=score,
            freeze_score=score,
            stability_score=score,
            overall_score=score,
            is_rejected=False,
            reject_reasons=[],
            tags=["product", "bright", "stable"],
        ),
    )
