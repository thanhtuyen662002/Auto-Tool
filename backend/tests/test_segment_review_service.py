from __future__ import annotations

from app import database
from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.source_media_manager.media_manager_schema import SegmentReviewStatus
from app.modules.source_media_manager.segment_review_service import SegmentReviewService
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


def test_segment_review_update_and_bulk_update(tmp_path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    config = _config(tmp_path)
    database.create_project("project-1", config.model_dump(mode="json"))
    source_path = str(tmp_path / "source.mp4")
    media = MediaFile(path=source_path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mov,mp4")
    segments = [_segment(source_path, "seg-1", 0.8), _segment(source_path, "seg-2", 0.4, rejected=True)]
    monkeypatch.setattr(
        "app.modules.source_media_manager.segment_review_service.build_scored_media_segments",
        lambda project_id, config=None: ([media], segments),
    )
    monkeypatch.setattr(
        "app.modules.source_media_manager.segment_review_service.generate_segment_thumbnail",
        lambda source_path, timestamp, output_path, width=240: output_path,
    )

    service = SegmentReviewService()
    favorite = service.update_segment_review("project-1", "seg-1", SegmentReviewStatus.favorite, "Cảnh rõ")
    updated_count = service.bulk_update_segment_review("project-1", ["seg-2"], SegmentReviewStatus.excluded)
    excluded = service.get_segment_review_items("project-1", status="excluded")

    assert favorite.review_status == SegmentReviewStatus.favorite
    assert updated_count == 1
    assert [item.segment_id for item in excluded] == ["seg-2"]


def test_segment_review_filters_by_min_score_and_tag(tmp_path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    config = _config(tmp_path)
    database.create_project("project-1", config.model_dump(mode="json"))
    source_path = str(tmp_path / "source.mp4")
    media = MediaFile(path=source_path, duration=8, width=1080, height=1920, fps=30, has_audio=True, format_name="mov,mp4")
    segments = [_segment(source_path, "seg-1", 0.85, tags=["sharp"]), _segment(source_path, "seg-2", 0.35, tags=["dark"])]
    monkeypatch.setattr(
        "app.modules.source_media_manager.segment_review_service.build_scored_media_segments",
        lambda project_id, config=None: ([media], segments),
    )
    monkeypatch.setattr(
        "app.modules.source_media_manager.segment_review_service.generate_segment_thumbnail",
        lambda source_path, timestamp, output_path, width=240: output_path,
    )

    items = SegmentReviewService().get_segment_review_items("project-1", min_score=0.8, tag="sharp")

    assert [item.segment_id for item in items] == ["seg-1"]


def _segment(path: str, segment_id: str, score: float, rejected: bool = False, tags: list[str] | None = None) -> VideoSegment:
    tags = tags or ["sharp"]
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
            tags=tags,
        ),
        tags=tags,
    )


def _config(tmp_path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "segment-review-test",
            "source_folder": str(tmp_path),
            "output_folder": str(tmp_path / "outputs"),
            "product": {"name": "Máy chiếu", "brand": "KAW", "description": "Mô tả.", "features": ["Gọn"], "cta": "Xem ngay"},
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
            "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi"},
        }
    )
