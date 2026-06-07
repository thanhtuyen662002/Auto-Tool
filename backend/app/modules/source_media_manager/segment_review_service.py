from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import database
from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.source_media_manager.media_manager_schema import (
    SegmentReviewItem,
    SegmentReviewStatus,
)
from app.modules.source_media_manager.media_manager_service import (
    build_scored_media_segments,
    normalize_media_path,
    project_config,
    segment_id,
    source_media_id,
    write_review_backups,
)
from app.schemas.media_schema import VideoSegment
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json
from app.utils.logger import get_logger


logger = get_logger(__name__)


class SegmentReviewService:
    def build_segment_review_items(self, project_id: str) -> list[SegmentReviewItem]:
        return self.get_segment_review_items(project_id)

    def get_segment_review_items(
        self,
        project_id: str,
        source_path: str | None = None,
        status: str | None = None,
        min_score: float | None = None,
        tag: str | None = None,
    ) -> list[SegmentReviewItem]:
        config = project_config(project_id)
        _, segments = build_scored_media_segments(project_id, config)
        crop_by_key = _crop_report_by_key(project_id)
        reviews = {item["segment_id"]: item for item in database.list_segment_reviews(project_id)}

        items: list[SegmentReviewItem] = []
        for segment in segments:
            item = _segment_item(project_id, config, segment, reviews, crop_by_key)
            if source_path and normalize_media_path(item.source_path) != normalize_media_path(source_path):
                continue
            if status and item.review_status.value != status:
                continue
            if min_score is not None and item.overall_score < min_score:
                continue
            if tag and tag not in item.tags:
                continue
            items.append(item)

        write_json(
            Path(config.output_folder) / "segment_reviews.json",
            {
                "project_id": project_id,
                "items": [item.model_dump(mode="json") for item in items],
            },
        )
        return sorted(items, key=lambda item: (Path(item.source_path).name.lower(), item.start))

    def update_segment_review(
        self,
        project_id: str,
        segment_id: str,
        review_status: SegmentReviewStatus,
        user_note: str | None = None,
    ) -> SegmentReviewItem:
        config = project_config(project_id)
        items = self.get_segment_review_items(project_id)
        target = next((item for item in items if item.segment_id == segment_id), None)
        if not target:
            raise ValueError(f"Không tìm thấy segment trong project: {segment_id}")
        database.upsert_segment_review(
            project_id=project_id,
            segment_id=target.segment_id,
            source_path=target.source_path,
            start=target.start,
            end=target.end,
            review_status=review_status.value,
            user_note=user_note,
        )
        write_review_backups(project_id, config)
        updated = self.get_segment_review_items(project_id)
        return next(item for item in updated if item.segment_id == segment_id)

    def bulk_update_segment_review(
        self,
        project_id: str,
        segment_ids: list[str],
        review_status: SegmentReviewStatus,
        user_note: str | None = None,
    ) -> int:
        if not segment_ids:
            return 0
        config = project_config(project_id)
        known = {item.segment_id: item for item in self.get_segment_review_items(project_id)}
        updated = 0
        for item_id in segment_ids:
            item = known.get(item_id)
            if not item:
                continue
            database.upsert_segment_review(
                project_id=project_id,
                segment_id=item.segment_id,
                source_path=item.source_path,
                start=item.start,
                end=item.end,
                review_status=review_status.value,
                user_note=user_note,
            )
            updated += 1
        write_review_backups(project_id, config)
        return updated


def generate_segment_thumbnail(
    source_path: str,
    timestamp: float,
    output_path: str,
    width: int = 240,
) -> str:
    target = Path(output_path)
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    ensure_dir(target.parent)
    run_ffmpeg(
        [
            "-y",
            "-ss",
            f"{max(0.0, timestamp):.3f}",
            "-i",
            source_path,
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-1",
            "-q:v",
            "3",
            str(target),
        ]
    )
    return str(target)


def _segment_item(
    project_id: str,
    config: ProjectConfig,
    segment: VideoSegment,
    reviews: dict[str, dict[str, Any]],
    crop_by_key: dict[str, dict[str, Any]],
) -> SegmentReviewItem:
    sid = segment.id or segment_id(segment.source_path, segment.start, segment.end)
    review = reviews.get(sid)
    score = segment.score_detail
    crop = crop_by_key.get(_segment_key(segment.source_path, segment.start, segment.end), {})
    warnings = list(crop.get("warnings") or [])
    thumbnail_path = _thumbnail_path(config, sid)
    try:
        preview_thumbnail_path = generate_segment_thumbnail(
            segment.source_path,
            segment.start + max(0.0, segment.duration / 2),
            str(thumbnail_path),
        )
    except (OSError, FFmpegError, ValueError) as exc:
        preview_thumbnail_path = None
        warning = f"thumbnail_failed: {exc}"
        warnings.append(warning)
        logger.warning("Không thể tạo thumbnail segment %s: %s", sid, exc)

    now = _now()
    reject_reasons = list(score.reject_reasons if score else [])
    return SegmentReviewItem(
        id=f"{project_id}:{sid}",
        project_id=project_id,
        segment_id=sid,
        source_media_id=source_media_id(segment.source_path),
        source_path=normalize_media_path(segment.source_path),
        start=round(segment.start, 3),
        end=round(segment.end, 3),
        duration=round(segment.duration, 3),
        overall_score=round(score.overall_score if score else segment.score, 3),
        brightness_score=score.brightness_score if score else None,
        sharpness_score=score.sharpness_score if score else None,
        motion_score=score.motion_score if score else None,
        freeze_score=score.freeze_score if score else None,
        stability_score=score.stability_score if score else None,
        crop_safety_score=crop.get("overall_safety_score"),
        crop_mode=crop.get("crop_mode"),
        tags=list(segment.tags),
        reject_reasons=reject_reasons,
        warnings=warnings,
        review_status=SegmentReviewStatus(review["review_status"]) if review else SegmentReviewStatus.pending,
        user_note=review.get("user_note") if review else None,
        preview_thumbnail_path=preview_thumbnail_path,
        created_at=str(review.get("created_at") if review else now),
        updated_at=str(review.get("updated_at") if review else now),
    )


def _thumbnail_path(config: ProjectConfig, segment_id_value: str) -> Path:
    safe_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in segment_id_value)
    return Path(config.output_folder) / config.project_name / "thumbnails" / f"segment_{safe_id}.jpg"


def _crop_report_by_key(project_id: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for report_path in _candidate_crop_reports(project_id):
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for clip in payload.get("clips", []):
            if not isinstance(clip, dict):
                continue
            result[_segment_key(clip.get("source_path", ""), float(clip.get("start") or 0), float(clip.get("end") or 0))] = clip
    return result


def _candidate_crop_reports(project_id: str) -> list[Path]:
    paths: list[Path] = []
    for job in database.get_project_jobs(project_id, include_preview=True):
        folder = job.get("output_folder")
        if not folder:
            continue
        path = Path(str(folder)) / "crop_safety_report.json"
        if path.exists():
            paths.append(path)
    return list(reversed(paths))


def _segment_key(source_path: str, start: float, end: float) -> str:
    return f"{normalize_media_path(source_path)}|{start:.3f}|{end:.3f}"


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
