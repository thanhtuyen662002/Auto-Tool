from __future__ import annotations

from app import database
from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.source_media_manager.media_filter_service import MediaFilterService
from app.schemas.media_schema import VideoSegment
from app.schemas.project_schema import ProjectConfig


def test_excluded_media_is_not_used_when_filtering_segments(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    source_a = str(tmp_path / "bad.mp4")
    source_b = str(tmp_path / "good.mp4")
    database.upsert_source_media_review("project-1", source_a, "excluded")

    result = MediaFilterService().filter_segments_for_render(
        "project-1",
        [_segment(source_a, "seg-a", 0.8), _segment(source_b, "seg-b", 0.8)],
        config=_config(tmp_path),
    )

    assert [segment.id for segment in result] == ["seg-b"]


def test_excluded_segment_is_not_used_when_filtering_segments(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    source = str(tmp_path / "source.mp4")
    database.upsert_segment_review("project-1", "seg-a", source, 0.5, 2.5, "excluded")

    result = MediaFilterService().filter_segments_for_render(
        "project-1",
        [_segment(source, "seg-a", 0.8), _segment(source, "seg-b", 0.7)],
        config=_config(tmp_path),
    )

    assert [segment.id for segment in result] == ["seg-b"]


def test_favorite_segment_is_prioritized_and_low_quality_warns(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    source = str(tmp_path / "source.mp4")
    database.upsert_segment_review("project-1", "seg-low", source, 0.5, 2.5, "favorite")
    logs: list[tuple[str, str]] = []

    result = MediaFilterService(log_callback=lambda level, message: logs.append((level, message))).filter_segments_for_render(
        "project-1",
        [_segment(source, "seg-good", 0.8), _segment(source, "seg-low", 0.2, rejected=True)],
        config=_config(tmp_path),
    )

    assert result[0].id == "seg-low"
    assert any(message == "favorite_segment_has_low_quality_score" for _, message in logs)


def test_excluded_fallback_is_not_used_by_default(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    source = str(tmp_path / "source.mp4")
    database.upsert_segment_review("project-1", "seg-a", source, 0.5, 2.5, "excluded")

    result = MediaFilterService().filter_segments_for_render(
        "project-1",
        [_segment(source, "seg-a", 0.8)],
        config=_config(tmp_path),
    )

    assert result == []


def _segment(path: str, segment_id: str, score: float, rejected: bool = False) -> VideoSegment:
    return VideoSegment(
        id=segment_id,
        source_path=path,
        start=0.5,
        end=2.5,
        duration=2.0,
        score=score,
        score_detail=SegmentScore(
            segment_id=segment_id,
            source_path=path,
            start=0.5,
            end=2.5,
            duration=2.0,
            brightness_score=score,
            sharpness_score=score,
            motion_score=score,
            freeze_score=score,
            stability_score=score,
            overall_score=score,
            is_rejected=rejected,
            reject_reasons=["low_quality_segment"] if rejected else [],
            tags=[],
        ),
    )


def _config(tmp_path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "media-filter-test",
            "source_folder": str(tmp_path),
            "output_folder": str(tmp_path / "outputs"),
            "product": {"name": "Máy chiếu", "brand": "KAW", "description": "Mô tả.", "features": ["Gọn"], "cta": "Xem ngay"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
            "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi"},
        }
    )
