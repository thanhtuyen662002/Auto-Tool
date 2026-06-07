from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app import database
from app.modules.source_media_manager.media_manager_schema import MediaReviewStatus, SegmentReviewStatus
from app.modules.source_media_manager.media_manager_service import normalize_media_path
from app.schemas.media_schema import VideoSegment
from app.schemas.project_schema import ProjectConfig


LogCallback = Callable[[str, str], None]


class MediaFilterService:
    def __init__(self, log_callback: LogCallback | None = None) -> None:
        self.log_callback = log_callback
        self.last_summary: dict[str, Any] = {}

    def filter_segments_for_render(
        self,
        project_id: str,
        segments: list[VideoSegment],
        config: ProjectConfig | None = None,
    ) -> list[VideoSegment]:
        if not segments:
            self.last_summary = _empty_summary()
            return []

        settings = config.source_media if config else None
        respect_exclusions = True if settings is None else settings.respect_user_exclusions
        prefer_favorites = True if settings is None else settings.prefer_favorite_segments
        allow_excluded_fallback = False if settings is None else settings.allow_excluded_fallback

        media_reviews = {
            normalize_media_path(item["media_path"]): item["review_status"]
            for item in database.list_source_media_reviews(project_id)
        }
        segment_reviews = {
            item["segment_id"]: item["review_status"]
            for item in database.list_segment_reviews(project_id)
        }

        annotated = [
            _annotate_segment(segment, media_reviews, segment_reviews)
            for segment in segments
        ]
        excluded_media_count = sum(1 for status in media_reviews.values() if status in _blocked_statuses())
        excluded_segment_count = sum(1 for status in segment_reviews.values() if status in _blocked_statuses())
        favorite_segments = [
            segment for segment in annotated if segment.user_review_status == SegmentReviewStatus.favorite.value
        ]

        allowed: list[VideoSegment] = []
        pending_fallback: list[VideoSegment] = []
        excluded_fallback: list[VideoSegment] = []
        for segment in annotated:
            media_blocked = segment.source_media_review_status in _blocked_statuses()
            segment_blocked = segment.user_review_status in _blocked_statuses()
            if respect_exclusions and (media_blocked or segment_blocked):
                excluded_fallback.append(segment)
                continue
            allowed.append(segment)
            if segment.user_review_status in {None, SegmentReviewStatus.pending.value}:
                pending_fallback.append(segment)

        if len(allowed) < 3:
            self._log("warning", "Số segment khả dụng sau lọc hơi ít; đang dùng thêm segment pending nếu có.")
            allowed_ids = {_segment_key(segment) for segment in allowed}
            for segment in pending_fallback:
                if _segment_key(segment) not in allowed_ids:
                    allowed.append(segment)
                    allowed_ids.add(_segment_key(segment))
                if len(allowed) >= 3:
                    break

        if not allowed and allow_excluded_fallback:
            self._log("warning", "Không còn segment sau lọc; allow_excluded_fallback đang bật nên dùng segment bị loại.")
            allowed = list(excluded_fallback)
        elif not allowed:
            self._log("warning", "Không còn segment sau lọc source media; render sẽ fail nếu không có segment khác.")

        if prefer_favorites:
            allowed.sort(key=_review_sort_key)

        low_quality_favorites = [
            segment
            for segment in allowed
            if segment.user_review_status == SegmentReviewStatus.favorite.value
            and _segment_score(segment) < 0.4
        ]
        if low_quality_favorites:
            self._log("warning", "favorite_segment_has_low_quality_score")

        self.last_summary = {
            "segments_before_filter": len(segments),
            "segments_after_filter": len(allowed),
            "excluded_media_count": excluded_media_count,
            "excluded_segment_count": excluded_segment_count,
            "favorite_segments_available": len(favorite_segments),
            "favorite_segments_used": 0,
            "respect_user_exclusions": respect_exclusions,
            "allow_excluded_fallback": allow_excluded_fallback,
            "warnings": ["favorite_segment_has_low_quality_score"] if low_quality_favorites else [],
        }
        return allowed

    def _log(self, level: str, message: str) -> None:
        if self.log_callback:
            self.log_callback(level, message)


def source_media_summary_for_filter(summary: dict[str, Any], total_media: int | None = None) -> dict[str, Any]:
    return {
        "total_media": total_media,
        "excluded_media": summary.get("excluded_media_count", 0),
        "total_segments": summary.get("segments_before_filter", 0),
        "segments_after_user_filter": summary.get("segments_after_filter", 0),
        "favorite_segments_used": summary.get("favorite_segments_used", 0),
        "favorite_segments_available": summary.get("favorite_segments_available", 0),
    }


def summarize_timeline_source_filter(timeline: Any, base_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = dict(base_summary or {})
    clips = list(getattr(timeline, "clips", []) or [])
    summary["favorite_segments_used"] = sum(
        1 for clip in clips if getattr(clip, "user_review_status", None) == SegmentReviewStatus.favorite.value
    )
    summary["good_segments_used"] = sum(
        1 for clip in clips if getattr(clip, "user_review_status", None) == SegmentReviewStatus.good.value
    )
    return summary


def _annotate_segment(
    segment: VideoSegment,
    media_reviews: dict[str, str],
    segment_reviews: dict[str, str],
) -> VideoSegment:
    media_status = media_reviews.get(normalize_media_path(segment.source_path), MediaReviewStatus.pending.value)
    segment_status = segment_reviews.get(segment.id, SegmentReviewStatus.pending.value)
    return segment.model_copy(
        update={
            "source_path": normalize_media_path(segment.source_path),
            "source_media_review_status": media_status,
            "user_review_status": segment_status,
        }
    )


def _review_sort_key(segment: VideoSegment) -> tuple[int, float]:
    priority = {
        SegmentReviewStatus.favorite.value: 0,
        SegmentReviewStatus.good.value: 1,
        SegmentReviewStatus.pending.value: 2,
        None: 2,
    }.get(segment.user_review_status, 3)
    return priority, -_segment_score(segment)


def _segment_score(segment: VideoSegment) -> float:
    if segment.score_detail is not None:
        return float(segment.score_detail.overall_score)
    return float(segment.score)


def _segment_key(segment: VideoSegment) -> str:
    return segment.id or f"{segment.source_path}|{segment.start:.3f}|{segment.end:.3f}"


def _blocked_statuses() -> set[str]:
    return {MediaReviewStatus.excluded.value, MediaReviewStatus.bad.value}


def _empty_summary() -> dict[str, Any]:
    return {
        "segments_before_filter": 0,
        "segments_after_filter": 0,
        "excluded_media_count": 0,
        "excluded_segment_count": 0,
        "favorite_segments_available": 0,
        "favorite_segments_used": 0,
        "warnings": [],
    }
