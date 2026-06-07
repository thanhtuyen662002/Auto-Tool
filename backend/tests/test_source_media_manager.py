from __future__ import annotations

from app import database
from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.source_media_manager.media_manager_schema import MediaReviewStatus
from app.modules.source_media_manager.media_manager_service import (
    MediaManagerService,
    build_source_media_items_from_data,
)
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig


def test_build_source_media_items_from_scan_and_scoring_report(tmp_path) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    config = _config(tmp_path)
    media = MediaFile(
        path=str(tmp_path / "source.mp4"),
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        format_name="mov,mp4",
    )
    segment = _segment(str(tmp_path / "source.mp4"), score=0.82)

    items = build_source_media_items_from_data("project-1", config, [media], [segment])

    assert len(items) == 1
    assert items[0].quality_score == 0.82
    assert items[0].segment_count == 1
    assert items[0].usable_segment_count == 1
    assert items[0].orientation == "vertical"


def test_update_media_status_excluded_is_persisted(tmp_path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    database.init_db()
    config = _config(tmp_path)
    database.create_project("project-1", config.model_dump(mode="json"))
    media = MediaFile(
        path=str(tmp_path / "source.mp4"),
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        format_name="mov,mp4",
    )
    segment = _segment(str(tmp_path / "source.mp4"), score=0.82)
    monkeypatch.setattr(
        "app.modules.source_media_manager.media_manager_service.build_scored_media_segments",
        lambda project_id, config=None: ([media], [segment]),
    )

    item = MediaManagerService().update_media_review(
        "project-1",
        str(tmp_path / "source.mp4"),
        MediaReviewStatus.excluded,
        "Không liên quan",
    )

    assert item.review_status == MediaReviewStatus.excluded
    assert database.get_source_media_review("project-1", item.path)["review_status"] == "excluded"


def _segment(path: str, score: float = 0.8, rejected: bool = False) -> VideoSegment:
    return VideoSegment(
        id="seg-1",
        source_path=path,
        start=0.5,
        end=2.5,
        duration=2.0,
        score=score,
        score_detail=SegmentScore(
            segment_id="seg-1",
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
            tags=["sharp"],
        ),
        tags=["sharp"],
    )


def _config(tmp_path) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "source-media-test",
            "source_folder": str(tmp_path),
            "output_folder": str(tmp_path / "outputs"),
            "product": {
                "name": "Máy chiếu",
                "brand": "KAW",
                "description": "Mô tả.",
                "features": ["Gọn"],
                "cta": "Xem ngay",
            },
            "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
            "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
            "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi"},
        }
    )
