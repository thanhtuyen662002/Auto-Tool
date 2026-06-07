from __future__ import annotations

from fastapi.testclient import TestClient

from app import database
from app.api import create_app
from app.modules.source_media_manager.media_manager_schema import (
    MediaReviewStatus,
    SegmentReviewItem,
    SegmentReviewStatus,
    SourceMediaItem,
    SourceMediaSummary,
)


def test_source_media_api_get_and_update(tmp_path, monkeypatch) -> None:
    database.DB_PATH = tmp_path / "autotool-test.db"
    config = _config(tmp_path)
    media_item = _media_item("project-1", str(tmp_path / "source.mp4"))
    segment_item = _segment_item("project-1", str(tmp_path / "source.mp4"))

    monkeypatch.setattr(
        "app.api.MediaManagerService.get_source_media_items",
        lambda self, project_id: [media_item],
    )
    monkeypatch.setattr(
        "app.api.MediaManagerService.update_media_review",
        lambda self, project_id, media_path, review_status, user_note=None: media_item.model_copy(update={"review_status": review_status}),
    )
    monkeypatch.setattr(
        "app.api.SegmentReviewService.get_segment_review_items",
        lambda self, project_id, source_path=None, status=None, min_score=None, tag=None: [segment_item]
        if (status in {None, "pending"} and (min_score is None or segment_item.overall_score >= min_score) and (tag is None or tag in segment_item.tags))
        else [],
    )
    monkeypatch.setattr(
        "app.api.SegmentReviewService.update_segment_review",
        lambda self, project_id, segment_id, review_status, user_note=None: segment_item.model_copy(update={"review_status": review_status}),
    )
    monkeypatch.setattr(
        "app.api.SegmentReviewService.bulk_update_segment_review",
        lambda self, project_id, segment_ids, review_status, user_note=None: len(segment_ids),
    )

    with TestClient(create_app()) as client:
        created = client.post("/api/projects", json=config)
        assert created.status_code == 200
        project_id = created.json()["project_id"]

        source = client.get(f"/api/projects/{project_id}/source-media")
        assert source.status_code == 200
        assert source.json()["summary"]["total_media"] == 1
        assert source.json()["items"][0]["filename"] == "source.mp4"

        media_update = client.put(
            f"/api/projects/{project_id}/source-media/review",
            json={"media_path": media_item.path, "review_status": "excluded", "user_note": "Loại"},
        )
        assert media_update.status_code == 200
        assert media_update.json()["item"]["review_status"] == "excluded"

        segments = client.get(f"/api/projects/{project_id}/segments", params={"min_score": 0.8, "tag": "sharp"})
        assert segments.status_code == 200
        assert segments.json()["items"][0]["segment_id"] == "seg-1"

        segment_update = client.put(
            f"/api/projects/{project_id}/segments/seg-1/review",
            json={"review_status": "favorite", "user_note": "Cảnh đẹp"},
        )
        assert segment_update.status_code == 200
        assert segment_update.json()["item"]["review_status"] == "favorite"

        bulk = client.post(
            f"/api/projects/{project_id}/segments/bulk-review",
            json={"segment_ids": ["seg-1"], "review_status": "excluded"},
        )
        assert bulk.status_code == 200
        assert bulk.json()["updated_count"] == 1


def _media_item(project_id: str, path: str) -> SourceMediaItem:
    return SourceMediaItem(
        id="media-1",
        project_id=project_id,
        path=path,
        filename="source.mp4",
        duration=8,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        format_name="mov,mp4",
        orientation="vertical",
        aspect_ratio="9:16",
        quality_score=0.82,
        segment_count=1,
        usable_segment_count=1,
        rejected_segment_count=0,
        review_status=MediaReviewStatus.pending,
        user_note=None,
        warnings=[],
        errors=[],
        created_at="2026-06-07T00:00:00",
        updated_at="2026-06-07T00:00:00",
    )


def _segment_item(project_id: str, source_path: str) -> SegmentReviewItem:
    return SegmentReviewItem(
        id=f"{project_id}:seg-1",
        project_id=project_id,
        segment_id="seg-1",
        source_media_id="media-1",
        source_path=source_path,
        start=0.5,
        end=2.5,
        duration=2.0,
        overall_score=0.82,
        brightness_score=0.8,
        sharpness_score=0.8,
        motion_score=0.8,
        freeze_score=0.8,
        stability_score=0.8,
        crop_safety_score=None,
        crop_mode=None,
        tags=["sharp"],
        reject_reasons=[],
        warnings=[],
        review_status=SegmentReviewStatus.pending,
        user_note=None,
        preview_thumbnail_path=None,
        created_at="2026-06-07T00:00:00",
        updated_at="2026-06-07T00:00:00",
    )


def _config(tmp_path) -> dict:
    return {
        "project_name": "source-media-api-test",
        "source_folder": str(tmp_path),
        "output_folder": str(tmp_path / "outputs"),
        "product": {"name": "Máy chiếu", "brand": "KAW", "description": "Mô tả.", "features": ["Gọn"], "cta": "Xem ngay"},
        "render": {"output_count": 1, "duration": 8, "aspect_ratio": "9:16", "resolution": "1080x1920", "fps": 30},
        "effects": {"cut_intensity": 70, "speed_variation": 30, "grain": 0, "zoom_motion": 0, "overlay_height": 33, "subtitle_size": 84},
        "ai": {"text_model": "gemini-test", "tone": "friendly_reviewer", "language": "vi"},
    }
