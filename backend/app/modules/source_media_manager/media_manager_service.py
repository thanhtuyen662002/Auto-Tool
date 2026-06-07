from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from app import database
from app.modules.cache.cache_service import CacheService
from app.modules.media_scanner.scanner import MediaScanner
from app.modules.segment_scoring.segment_scorer import SegmentScorer
from app.modules.segmenter.segmenter import Segmenter
from app.modules.source_media_manager.media_manager_schema import (
    MediaReviewStatus,
    SourceMediaItem,
    SourceMediaSummary,
)
from app.schemas.media_schema import MediaFile, VideoSegment
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir, write_json


class MediaManagerService:
    def build_source_media_items(self, project_id: str) -> list[SourceMediaItem]:
        return self.get_source_media_items(project_id)

    def get_source_media_items(self, project_id: str) -> list[SourceMediaItem]:
        config = project_config(project_id)
        media_files, segments = build_scored_media_segments(project_id, config)
        return build_source_media_items_from_data(project_id, config, media_files, segments)

    def update_media_review(
        self,
        project_id: str,
        media_path: str,
        review_status: MediaReviewStatus,
        user_note: str | None = None,
    ) -> SourceMediaItem:
        config = project_config(project_id)
        normalized_path = normalize_media_path(media_path)
        database.upsert_source_media_review(
            project_id=project_id,
            media_path=normalized_path,
            review_status=review_status.value,
            user_note=user_note,
        )
        write_review_backups(project_id, config)
        for item in self.get_source_media_items(project_id):
            if item.path == normalized_path:
                return item
        raise ValueError(f"Không tìm thấy video nguồn trong project: {media_path}")

    def get_summary(self, project_id: str) -> SourceMediaSummary:
        return build_source_media_summary(self.get_source_media_items(project_id), [])


def build_source_media_items_from_data(
    project_id: str,
    config: ProjectConfig,
    media_files: list[MediaFile],
    segments: list[VideoSegment],
) -> list[SourceMediaItem]:
    reviews = {normalize_media_path(item["media_path"]): item for item in database.list_source_media_reviews(project_id)}
    grouped: dict[str, list[VideoSegment]] = defaultdict(list)
    for segment in segments:
        grouped[normalize_media_path(segment.source_path)].append(segment)

    now = _now()
    items: list[SourceMediaItem] = []
    for media in media_files:
        path = normalize_media_path(media.path)
        review = reviews.get(path)
        media_segments = grouped.get(path, [])
        scored = [segment for segment in media_segments if segment.score_detail is not None]
        usable = [
            segment
            for segment in scored
            if segment.score_detail is not None and not segment.score_detail.is_rejected
        ]
        rejected = [
            segment
            for segment in scored
            if segment.score_detail is not None and segment.score_detail.is_rejected
        ]
        scores = [segment.score_detail.overall_score for segment in scored if segment.score_detail is not None]
        warnings: list[str] = []
        if media.duration < 5:
            warnings.append("video_duration_short")
        if media.width < media.height and media.width < 720:
            warnings.append("low_vertical_resolution")
        if scores and sum(scores) / len(scores) < 0.45:
            warnings.append("low_average_segment_score")

        item = SourceMediaItem(
            id=source_media_id(path),
            project_id=project_id,
            path=path,
            filename=Path(path).name,
            duration=round(media.duration, 3),
            width=media.width,
            height=media.height,
            fps=round(media.fps, 3),
            has_audio=media.has_audio,
            format_name=media.format_name,
            orientation=orientation(media.width, media.height),
            aspect_ratio=aspect_ratio(media.width, media.height),
            quality_score=round(sum(scores) / len(scores), 3) if scores else None,
            segment_count=len(media_segments),
            usable_segment_count=len(usable),
            rejected_segment_count=len(rejected),
            review_status=MediaReviewStatus(review["review_status"]) if review else MediaReviewStatus.pending,
            user_note=review.get("user_note") if review else None,
            warnings=warnings,
            errors=[],
            created_at=str(review.get("created_at") if review else now),
            updated_at=str(review.get("updated_at") if review else now),
        )
        items.append(item)

    write_json(
        Path(config.output_folder) / "source_media_reviews.json",
        {
            "project_id": project_id,
            "items": [item.model_dump(mode="json") for item in items],
        },
    )
    return sorted(items, key=lambda item: item.filename.lower())


def build_source_media_summary(
    media_items: list[SourceMediaItem],
    segment_items: list[Any],
) -> SourceMediaSummary:
    media_scores = [item.quality_score for item in media_items if item.quality_score is not None]
    segment_scores = [
        getattr(item, "overall_score")
        for item in segment_items
        if getattr(item, "overall_score", None) is not None
    ]
    total_segments = sum(item.segment_count for item in media_items)
    usable_segments = sum(item.usable_segment_count for item in media_items)
    excluded_segments = sum(
        1
        for item in segment_items
        if str(getattr(item, "review_status", "")) in {"SegmentReviewStatus.excluded", "excluded"}
    )
    favorite_segments = sum(
        1
        for item in segment_items
        if str(getattr(item, "review_status", "")) in {"SegmentReviewStatus.favorite", "favorite"}
    )
    return SourceMediaSummary(
        total_media=len(media_items),
        good_media=sum(1 for item in media_items if item.review_status == MediaReviewStatus.good),
        excluded_media=sum(1 for item in media_items if item.review_status == MediaReviewStatus.excluded),
        bad_media=sum(1 for item in media_items if item.review_status == MediaReviewStatus.bad),
        total_segments=total_segments,
        usable_segments=usable_segments,
        excluded_segments=excluded_segments,
        favorite_segments=favorite_segments,
        average_media_score=round(sum(media_scores) / len(media_scores), 3) if media_scores else None,
        average_segment_score=round(sum(segment_scores) / len(segment_scores), 3) if segment_scores else None,
    )


def build_scored_media_segments(
    project_id: str,
    config: ProjectConfig | None = None,
) -> tuple[list[MediaFile], list[VideoSegment]]:
    config = config or project_config(project_id)
    cache_service = CacheService.for_project(config)
    media_files = MediaScanner(
        cache_service=cache_service,
        cache_enabled=config.cache.cache_media_metadata,
    ).scan_folder(config.source_folder)
    segments = Segmenter().create_segments(media_files, config.effects.cut_intensity)
    scored_segments = SegmentScorer(
        cache_service=cache_service,
        cache_enabled=config.cache.cache_segment_scoring,
        settings_hash=cache_service.settings_hash(
            {
                "scorer": "segment_scorer_v1",
                "max_frames": 5,
                "resolution": config.render.resolution,
            }
        ),
    ).score_segments(segments)
    return media_files, scored_segments


def project_config(project_id: str) -> ProjectConfig:
    project = database.get_project(project_id)
    if not project:
        raise ValueError(f"Không tìm thấy project: {project_id}")
    return ProjectConfig.model_validate(project["config"])


def normalize_media_path(path: str) -> str:
    try:
        return str(Path(path).expanduser().resolve())
    except OSError:
        return str(Path(path).expanduser())


def source_media_id(path: str) -> str:
    return hashlib.sha1(normalize_media_path(path).encode("utf-8")).hexdigest()[:16]


def segment_id(source_path: str, start: float, end: float) -> str:
    raw_value = f"{normalize_media_path(source_path)}|{start:.3f}|{end:.3f}"
    return hashlib.sha1(raw_value.encode("utf-8")).hexdigest()[:12]


def orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "vertical" if height > width else "horizontal"


def aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def write_review_backups(project_id: str, config: ProjectConfig) -> None:
    output_dir = ensure_dir(config.output_folder)
    write_json(
        output_dir / "source_media_reviews.json",
        {
            "project_id": project_id,
            "reviews": database.list_source_media_reviews(project_id),
        },
    )
    write_json(
        output_dir / "segment_reviews.json",
        {
            "project_id": project_id,
            "reviews": database.list_segment_reviews(project_id),
        },
    )


def _now() -> str:
    from datetime import datetime

    return datetime.now().replace(microsecond=0).isoformat()
