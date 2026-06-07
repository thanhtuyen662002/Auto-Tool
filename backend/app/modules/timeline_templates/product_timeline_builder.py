from __future__ import annotations

import random

from app.modules.timeline_builder.timeline_builder import Timeline, TimelineBuilder, TimelineClip
from app.modules.timeline_templates.template_registry import DEFAULT_TEMPLATE_ID, get_timeline_template
from app.modules.timeline_templates.template_schema import TimelineSlot
from app.schemas.media_schema import VideoSegment


class ProductTimelineBuilder:
    def build_timelines(
        self,
        segments: list[VideoSegment],
        output_count: int,
        target_duration: float,
        template_id: str,
        speed_variation: int,
    ) -> list[Timeline]:
        if not segments:
            raise ValueError("Cannot build product timelines because no segments are available.")
        if output_count <= 0:
            raise ValueError("output_count must be greater than 0.")
        if target_duration <= 0:
            raise ValueError("target_duration must be greater than 0.")

        template = get_timeline_template(template_id or DEFAULT_TEMPLATE_ID)
        timelines: list[Timeline] = []
        for output_index in range(1, output_count + 1):
            rng = random.Random(30_000 + output_index)
            clips = self._build_one_timeline(
                segments=segments,
                target_duration=target_duration,
                speed_variation=speed_variation,
                slots=template.slots,
                rng=rng,
            )
            timelines.append(
                Timeline(
                    output_index=output_index,
                    target_duration=target_duration,
                    template_id=template.id,
                    clips=clips,
                )
            )
        return timelines

    def _build_one_timeline(
        self,
        segments: list[VideoSegment],
        target_duration: float,
        speed_variation: int,
        slots: list[TimelineSlot],
        rng: random.Random,
    ) -> list[TimelineClip]:
        selected: list[TimelineClip] = []
        used_sources: list[str] = []
        used_segment_ids: set[str] = set()
        elapsed = 0.0
        max_iterations = max(1000, len(segments) * len(slots) * 10)
        iterations = 0

        for slot in slots:
            slot_target_duration = target_duration * (slot.end_ratio - slot.start_ratio)
            slot_elapsed = 0.0

            while slot_elapsed < slot_target_duration - 0.01 and elapsed < target_duration - 0.01:
                iterations += 1
                if iterations > max_iterations:
                    raise RuntimeError(
                        "Product timeline builder exceeded the safety iteration limit. "
                        f"elapsed={elapsed:.6f}, target_duration={target_duration:.6f}, segments={len(segments)}"
                    )

                segment = select_segment_for_slot(
                    candidates=segments,
                    slot=slot,
                    used_sources=used_sources,
                    used_segment_ids=used_segment_ids,
                    random_seed=rng.randint(1, 2_000_000_000),
                )
                speed = TimelineBuilder._pick_speed(speed_variation, rng)
                remaining_slot = slot_target_duration - slot_elapsed
                remaining_total = target_duration - elapsed
                desired_render_duration = min(remaining_slot, remaining_total, slot.max_clip_duration)
                if desired_render_duration <= 0.01:
                    break

                raw_duration = min(segment.duration, desired_render_duration * speed)
                rendered_duration = raw_duration / speed
                if rendered_duration <= 0.05:
                    break

                end = min(segment.start + raw_duration, segment.end)
                rendered_duration = (end - segment.start) / speed
                clip_duration = round(rendered_duration, 3)
                if clip_duration <= 0:
                    break

                segment_score = _quality_score(segment)
                selected.append(
                    TimelineClip(
                        segment_id=_segment_key(segment),
                        source_path=segment.source_path,
                        start=round(segment.start, 3),
                        end=round(end, 3),
                        duration=clip_duration,
                        speed=round(speed, 3),
                        slot_name=slot.name,
                        text_role=slot.text_role,
                        segment_score=round(segment_score, 3),
                        segment_score_cache_hit=segment.score_detail.cache_hit if segment.score_detail else False,
                        tags=list(segment.tags),
                        user_review_status=segment.user_review_status,
                        source_media_review_status=segment.source_media_review_status,
                    )
                )
                used_sources.append(segment.source_path)
                used_segment_ids.add(_segment_key(segment))
                elapsed += rendered_duration
                slot_elapsed += rendered_duration

        if not selected:
            raise ValueError("Product timeline builder could not select any clips.")
        return selected


def select_segment_for_slot(
    candidates: list[VideoSegment],
    slot: TimelineSlot,
    used_sources: list[str],
    random_seed: int,
    used_segment_ids: set[str] | None = None,
) -> VideoSegment:
    if not candidates:
        raise ValueError("Cannot select segment because candidates is empty.")

    candidate_pool = list(candidates)
    used_segment_ids = used_segment_ids or set()
    unused_candidates = [
        segment
        for segment in candidate_pool
        if _segment_key(segment) not in used_segment_ids
    ]
    if unused_candidates:
        candidate_pool = unused_candidates

    recent_sources = set(used_sources[-2:])
    source_alternatives = [
        segment
        for segment in candidate_pool
        if segment.source_path not in recent_sources
    ]
    if source_alternatives:
        candidate_pool = source_alternatives

    if len(used_sources) >= 2 and used_sources[-1] == used_sources[-2]:
        alternatives = [segment for segment in candidate_pool if segment.source_path != used_sources[-1]]
        if alternatives:
            candidate_pool = alternatives

    scored_candidates = [
        (segment, _selection_score(segment, slot, used_sources, used_segment_ids))
        for segment in candidate_pool
    ]
    scored_candidates.sort(key=lambda item: item[1], reverse=True)
    top_candidates = scored_candidates[: min(8, len(scored_candidates))]
    rng = random.Random(random_seed)
    weights = [max(0.05, score) ** 2 for _, score in top_candidates]
    return rng.choices([segment for segment, _ in top_candidates], weights=weights, k=1)[0]


def _selection_score(
    segment: VideoSegment,
    slot: TimelineSlot,
    used_sources: list[str],
    used_segment_ids: set[str] | None = None,
) -> float:
    quality_score = _quality_score(segment)
    tag_match_score = _tag_match_score(segment.tags, slot.preferred_tags, slot.avoided_tags)
    source_diversity_score = _source_diversity_score(segment.source_path, used_sources)
    duration_fit_score = _duration_fit_score(segment.duration, slot)
    repeat_penalty = 0.35 if used_segment_ids and _segment_key(segment) in used_segment_ids else 1.0
    review_boost = 1.0
    if segment.user_review_status == "favorite":
        review_boost = 2.2
    elif segment.user_review_status == "good":
        review_boost = 1.45
    return review_boost * repeat_penalty * (
        quality_score * 0.55
        + tag_match_score * 0.25
        + source_diversity_score * 0.15
        + duration_fit_score * 0.05
    )


def _quality_score(segment: VideoSegment) -> float:
    if segment.score_detail is not None:
        return max(0.0, min(1.0, segment.score_detail.overall_score))
    return max(0.0, min(1.0, segment.score))


def _tag_match_score(tags: list[str], preferred_tags: list[str], avoided_tags: list[str]) -> float:
    tag_set = set(tags)
    if preferred_tags:
        preferred_score = sum(1 for tag in preferred_tags if tag in tag_set) / len(preferred_tags)
    else:
        preferred_score = 0.5
    if any(tag in tag_set for tag in avoided_tags):
        preferred_score *= 0.4
    return preferred_score


def _duration_fit_score(duration: float, slot: TimelineSlot) -> float:
    if slot.min_clip_duration <= duration <= slot.max_clip_duration:
        return 1.0
    if duration < slot.min_clip_duration:
        return max(0.0, duration / slot.min_clip_duration)
    return max(0.2, slot.max_clip_duration / duration)


def _source_diversity_score(source_path: str, used_sources: list[str]) -> float:
    if not used_sources:
        return 1.0
    if source_path == used_sources[-1]:
        return 0.15
    if source_path in set(used_sources[-2:]):
        return 0.45
    return 1.0


def _segment_key(segment: VideoSegment) -> str:
    return segment.id or f"{segment.source_path}|{segment.start:.3f}|{segment.end:.3f}"
