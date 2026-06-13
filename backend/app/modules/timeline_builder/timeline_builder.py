from __future__ import annotations

import random

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

from app.modules.crop_safety.crop_schema import CropBox
from app.schemas.media_schema import VideoSegment


class ClipType(str, Enum):
    NORMAL = "normal"
    FREEZE = "freeze"
    FREEZE_ZOOM = "freeze_zoom"


class TimelineClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str | None = None
    source_path: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    duration: float = Field(gt=0)
    speed: float = Field(gt=0)
    slot_name: str | None = None
    text_role: str | None = None
    segment_score: float | None = None
    segment_score_cache_hit: bool | None = None
    tags: list[str] = Field(default_factory=list)
    crop_box: CropBox | None = None
    crop_mode: str | None = None
    crop_safety_score: float | None = None
    crop_warnings: list[str] = Field(default_factory=list)
    effective_zoom_motion: int | None = None
    crop_cache_hit: bool | None = None
    user_review_status: str | None = None
    source_media_review_status: str | None = None
    clip_type: ClipType = ClipType.NORMAL


class Timeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_index: int = Field(gt=0)
    target_duration: float = Field(gt=0)
    template_id: str | None = None
    clips: list[TimelineClip] = Field(min_length=1)


class TimelineBuilder:
    def build_timelines(
        self,
        segments: list[VideoSegment],
        output_count: int,
        target_duration: float,
        speed_variation: int,
    ) -> list[Timeline]:
        if not segments:
            raise ValueError("Cannot build timelines because no segments are available.")
        if output_count <= 0:
            raise ValueError("output_count must be greater than 0.")
        if target_duration <= 0:
            raise ValueError("target_duration must be greater than 0.")

        timelines: list[Timeline] = []
        for output_index in range(1, output_count + 1):
            rng = random.Random(10_000 + output_index)
            clips = self._build_one_timeline(
                segments=segments,
                target_duration=target_duration,
                speed_variation=speed_variation,
                rng=rng,
            )
            timelines.append(
                Timeline(
                    output_index=output_index,
                    target_duration=target_duration,
                    clips=clips,
                )
            )
        return timelines

    def _build_one_timeline(
        self,
        segments: list[VideoSegment],
        target_duration: float,
        speed_variation: int,
        rng: random.Random,
    ) -> list[TimelineClip]:
        selected: list[TimelineClip] = []
        elapsed = 0.0
        consecutive_source = ""
        consecutive_count = 0
        iterations = 0
        max_iterations = max(1000, len(segments) * 20)

        while elapsed < target_duration:
            iterations += 1
            if iterations > max_iterations:
                raise RuntimeError(
                    "Timeline builder exceeded the safety iteration limit. "
                    f"elapsed={elapsed:.6f}, target_duration={target_duration:.6f}, segments={len(segments)}"
                )

            remaining_duration = target_duration - elapsed
            if remaining_duration < 0.01:
                break

            segment = self._pick_weighted_segment(segments, consecutive_source, consecutive_count, rng)
            speed = self._pick_speed(speed_variation, rng)

            max_rendered_duration = segment.duration / speed
            rendered_duration = min(max_rendered_duration, remaining_duration)
            raw_duration = rendered_duration * speed
            end = min(segment.start + raw_duration, segment.end)
            rendered_duration = (end - segment.start) / speed

            clipped_duration = round(rendered_duration, 3)
            clipped_end = round(end, 3)
            clipped_start = round(segment.start, 3)
            if clipped_duration <= 0 or clipped_end <= clipped_start:
                break

            selected.append(
                TimelineClip(
                    segment_id=segment.id or None,
                    source_path=segment.source_path,
                    start=clipped_start,
                    end=clipped_end,
                    duration=clipped_duration,
                    speed=round(speed, 3),
                    user_review_status=segment.user_review_status,
                    source_media_review_status=segment.source_media_review_status,
                )
            )
            elapsed += rendered_duration

            if segment.source_path == consecutive_source:
                consecutive_count += 1
            else:
                consecutive_source = segment.source_path
                consecutive_count = 1

        return selected

    @staticmethod
    def _pick_weighted_segment(
        all_segments: list[VideoSegment],
        consecutive_source: str,
        consecutive_count: int,
        rng: random.Random,
    ) -> VideoSegment:
        candidates = list(all_segments)
        if consecutive_count >= 2:
            alternatives = [segment for segment in candidates if segment.source_path != consecutive_source]
            if alternatives:
                candidates = alternatives

        weights = [TimelineBuilder._segment_weight(segment) for segment in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]

    @staticmethod
    def _segment_weight(segment: VideoSegment) -> float:
        if segment.score_detail is not None:
            score = max(0.1, segment.score_detail.overall_score)
        else:
            score = max(0.1, segment.score)
        if segment.user_review_status == "favorite":
            return score * 2.2
        if segment.user_review_status == "good":
            return score * 1.5
        return score

    @staticmethod
    def _pick_speed(speed_variation: int, rng: random.Random) -> float:
        speed_variation = max(0, min(100, speed_variation))
        if speed_variation <= 0:
            return 1.0
        if speed_variation <= 30:
            low, high = 0.97, 1.05
        elif speed_variation <= 70:
            low, high = 0.93, 1.1
        else:
            low, high = 0.9, 1.15
        return rng.uniform(low, high)
