from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from app.modules.segment_scoring.frame_sampler import FrameSampler
from app.modules.segment_scoring.scoring_schema import SegmentScore
from app.modules.segment_scoring.segment_analyzer import SegmentAnalyzer
from app.schemas.media_schema import VideoSegment
from app.utils.logger import get_logger


logger = get_logger(__name__)


class SegmentScorer:
    def __init__(
        self,
        sampler: FrameSampler | None = None,
        analyzer: SegmentAnalyzer | None = None,
        max_frames: int = 5,
    ) -> None:
        self.sampler = sampler or FrameSampler()
        self.analyzer = analyzer or SegmentAnalyzer()
        self.max_frames = max_frames

    def score_segment(self, segment: VideoSegment) -> SegmentScore:
        segment_id = segment.id or _segment_id(segment)
        try:
            frames = self.sampler.sample_frames(segment.source_path, segment.start, segment.end, self.max_frames)
            if not frames:
                return self._rejected_score(segment, segment_id, ["no_frames"])

            metrics = self.analyzer.analyze_frames(frames)
            score = self._build_score(segment, segment_id, metrics)
            return score
        except Exception as exc:
            logger.warning(
                "Segment scoring failed for %s %.3f-%.3f: %s",
                segment.source_path,
                segment.start,
                segment.end,
                exc,
            )
            return self._rejected_score(segment, segment_id, ["analysis_failed"])

    def score_segments(self, segments: list[VideoSegment]) -> list[VideoSegment]:
        scored: list[VideoSegment] = []
        for segment in segments:
            detail = self.score_segment(segment)
            scored.append(
                segment.model_copy(
                    update={
                        "id": detail.segment_id,
                        "score": detail.overall_score,
                        "score_detail": detail,
                        "tags": detail.tags,
                    }
                )
            )
        return scored

    def _build_score(self, segment: VideoSegment, segment_id: str, metrics: dict[str, Any]) -> SegmentScore:
        brightness_score = float(metrics["brightness_score"])
        sharpness_score = float(metrics["sharpness_score"])
        motion_score = float(metrics["motion_score"])
        freeze_score = float(metrics["freeze_score"])
        stability_score = float(metrics["stability_score"])
        overall_score = round(
            brightness_score * 0.25
            + sharpness_score * 0.25
            + motion_score * 0.20
            + freeze_score * 0.20
            + stability_score * 0.10,
            3,
        )
        reject_reasons = self._reject_reasons(
            brightness_score,
            sharpness_score,
            freeze_score,
            overall_score,
        )
        tags = self._tags(brightness_score, sharpness_score, motion_score, stability_score)
        return SegmentScore(
            segment_id=segment_id,
            source_path=segment.source_path,
            start=segment.start,
            end=segment.end,
            duration=segment.duration,
            brightness_score=brightness_score,
            sharpness_score=sharpness_score,
            motion_score=motion_score,
            freeze_score=freeze_score,
            stability_score=stability_score,
            overall_score=overall_score,
            is_rejected=bool(reject_reasons),
            reject_reasons=reject_reasons,
            tags=tags,
        )

    @staticmethod
    def _rejected_score(segment: VideoSegment, segment_id: str, reasons: list[str]) -> SegmentScore:
        return SegmentScore(
            segment_id=segment_id,
            source_path=segment.source_path,
            start=segment.start,
            end=segment.end,
            duration=segment.duration,
            brightness_score=0.0,
            sharpness_score=0.0,
            motion_score=0.0,
            freeze_score=0.0,
            stability_score=0.0,
            overall_score=0.0,
            is_rejected=True,
            reject_reasons=reasons,
            tags=[],
        )

    @staticmethod
    def _reject_reasons(
        brightness_score: float,
        sharpness_score: float,
        freeze_score: float,
        overall_score: float,
    ) -> list[str]:
        reasons: list[str] = []
        if brightness_score < 0.25:
            reasons.append("too_dark_or_overexposed")
        if sharpness_score < 0.25:
            reasons.append("too_blurry")
        if freeze_score < 0.30:
            reasons.append("freeze_or_static")
        if overall_score < 0.40:
            reasons.append("low_quality_segment")
        return reasons

    @staticmethod
    def _tags(
        brightness_score: float,
        sharpness_score: float,
        motion_score: float,
        stability_score: float,
    ) -> list[str]:
        tags: list[str] = []
        if motion_score > 0.75:
            tags.append("high_motion")
        elif motion_score < 0.35:
            tags.append("low_motion")

        if brightness_score > 0.75:
            tags.append("bright")
        elif brightness_score < 0.35:
            tags.append("dark")

        if sharpness_score > 0.75:
            tags.append("sharp")
        elif sharpness_score < 0.35:
            tags.append("blurry")

        if stability_score > 0.75:
            tags.append("stable")
        elif stability_score < 0.45:
            tags.append("unstable")
        return tags


def build_scoring_report(segments: list[VideoSegment]) -> dict[str, Any]:
    scored_segments = [segment for segment in segments if segment.score_detail is not None]
    usable = [segment for segment in scored_segments if not segment.score_detail.is_rejected]
    rejected = [segment for segment in scored_segments if segment.score_detail.is_rejected]
    rejection_summary: Counter[str] = Counter()
    for segment in rejected:
        rejection_summary.update(segment.score_detail.reject_reasons)

    average_score = (
        round(sum(segment.score_detail.overall_score for segment in scored_segments) / len(scored_segments), 3)
        if scored_segments
        else 0.0
    )
    top_segments = sorted(
        scored_segments,
        key=lambda segment: segment.score_detail.overall_score,
        reverse=True,
    )[:10]
    return {
        "total_segments": len(segments),
        "usable_segments": len(usable),
        "rejected_segments": len(rejected),
        "average_score": average_score,
        "rejection_summary": dict(sorted(rejection_summary.items())),
        "top_segments": [
            {
                "source_path": segment.source_path,
                "start": segment.start,
                "end": segment.end,
                "overall_score": segment.score_detail.overall_score,
                "tags": segment.tags,
            }
            for segment in top_segments
        ],
    }


def _segment_id(segment: VideoSegment) -> str:
    raw_value = f"{segment.source_path}|{segment.start:.3f}|{segment.end:.3f}".encode("utf-8")
    return hashlib.sha1(raw_value).hexdigest()[:12]
