from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment
from app.modules.silent_visual_tagging.keyword_tag_mapper import KeywordTagMapper
from app.modules.silent_visual_tagging.visual_tag_rules import VisualTagRules
from app.modules.silent_visual_tagging.visual_tag_schema import (
    SegmentVisualTagResult,
    VideoVisualTagReport,
    VisualTag,
    VisualTagCategory,
)


class VisualTagService:
    def __init__(
        self,
        keyword_mapper: KeywordTagMapper | None = None,
        rules: VisualTagRules | None = None,
    ) -> None:
        self.keyword_mapper = keyword_mapper or KeywordTagMapper()
        self.rules = rules or VisualTagRules()

    def tag_video_segments(
        self,
        video_path: str,
        segments: list[SilentVisualSegment],
        product_context: dict | None = None,
        folder_name: str | None = None,
        filename: str | None = None,
        ocr_text_by_segment: dict[str, str] | None = None,
        project_id: str | None = None,
        job_id: str | None = None,
    ) -> VideoVisualTagReport:
        path = Path(video_path)
        product_text = _product_context_text(product_context)
        folder_text = folder_name if folder_name is not None else path.parent.name
        filename_text = filename if filename is not None else path.stem
        global_tags = [
            *self.keyword_mapper.tags_from_text(product_text, "product_context"),
            *self.keyword_mapper.tags_from_text(folder_text, "folder_name"),
            *self.keyword_mapper.tags_from_text(filename_text, "filename"),
        ]
        results: list[SegmentVisualTagResult] = []
        for index, segment in enumerate(segments):
            ocr_text = (ocr_text_by_segment or {}).get(segment.id) or segment.ocr_text or ""
            results.append(
                self.tag_segment(
                    segment,
                    segment_index=index,
                    total_segments=len(segments),
                    product_context=product_context,
                    text_context=ocr_text,
                    inherited_tags=global_tags,
                )
            )
        video_tags = _aggregate_video_tags(results, global_tags)
        recommended_industry = _primary(video_tags, VisualTagCategory.industry) or "general_product"
        average_confidence = (
            sum(result.confidence for result in results) / len(results)
            if results
            else _average_tag_confidence(video_tags)
        )
        warnings = [] if results else ["No visual segments available for tagging."]
        return VideoVisualTagReport(
            video_path=video_path,
            project_id=project_id,
            job_id=job_id,
            segment_results=results,
            video_level_tags=video_tags,
            recommended_industry=recommended_industry,
            recommended_strategy=_recommended_strategy(results),
            average_confidence=round(average_confidence, 4),
            warnings=warnings,
            created_at=datetime.now().replace(microsecond=0).isoformat(),
        )

    def tag_segment(
        self,
        segment: SilentVisualSegment,
        segment_index: int,
        total_segments: int,
        product_context: dict | None = None,
        text_context: str | None = None,
        inherited_tags: list[VisualTag] | None = None,
    ) -> SegmentVisualTagResult:
        tags = [
            *(inherited_tags or self.keyword_mapper.tags_from_text(_product_context_text(product_context), "product_context")),
            *self.keyword_mapper.tags_from_text(text_context or segment.ocr_text or "", "ocr_text"),
            *self.rules.tags_from_segment_features(segment, segment_index, total_segments),
        ]
        deduped = _merge_tags(tags)
        primary_industry = _primary(deduped, VisualTagCategory.industry)
        primary_scene = _primary(deduped, VisualTagCategory.scene)
        primary_action = _primary(deduped, VisualTagCategory.action)
        relevant = [tag.confidence for tag in deduped if tag.category != VisualTagCategory.quality]
        confidence = sum(relevant) / len(relevant) if relevant else _average_tag_confidence(deduped)
        warnings = [] if deduped else ["No visual tags matched this segment."]
        return SegmentVisualTagResult(
            segment_id=segment.id,
            video_path=segment.video_path,
            start=segment.start,
            end=segment.end,
            tags=deduped,
            primary_industry=primary_industry,
            primary_scene=primary_scene,
            primary_action=primary_action,
            confidence=round(confidence, 4),
            warnings=warnings,
        )

    @staticmethod
    def apply_report_to_segments(
        segments: list[SilentVisualSegment],
        report: VideoVisualTagReport,
    ) -> list[SilentVisualSegment]:
        by_id = {result.segment_id: result for result in report.segment_results}
        return [
            segment.model_copy(
                update={
                    "visual_tags": by_id[segment.id].tags,
                    "primary_industry": by_id[segment.id].primary_industry,
                    "primary_scene": by_id[segment.id].primary_scene,
                    "primary_action": by_id[segment.id].primary_action,
                    "visual_tag_confidence": by_id[segment.id].confidence,
                }
            )
            if segment.id in by_id
            else segment
            for segment in segments
        ]


def _product_context_text(context: dict | None) -> str:
    context = context or {}
    values = [
        context.get("industry"),
        context.get("category"),
        context.get("product_name"),
        context.get("name"),
        context.get("description"),
        context.get("features"),
    ]
    parts: list[str] = []
    for value in values:
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _merge_tags(tags: list[VisualTag]) -> list[VisualTag]:
    grouped: dict[str, list[VisualTag]] = defaultdict(list)
    for tag in tags:
        grouped[tag.tag].append(tag)
    result: list[VisualTag] = []
    for name, evidence in grouped.items():
        confidence_left = 1.0
        for tag in evidence:
            confidence_left *= 1.0 - tag.confidence
        strongest = max(evidence, key=lambda item: item.confidence)
        sources = list(dict.fromkeys(item.source for item in evidence))
        result.append(
            strongest.model_copy(
                update={
                    "confidence": round(min(1.0, 1.0 - confidence_left), 4),
                    "reason": f"Sources: {', '.join(sources)}",
                }
            )
        )
    return sorted(result, key=lambda item: (-item.confidence, item.category.value, item.tag))


def _aggregate_video_tags(
    results: list[SegmentVisualTagResult],
    global_tags: list[VisualTag],
) -> list[VisualTag]:
    return _merge_tags([*global_tags, *[tag for result in results for tag in result.tags]])


def _primary(tags: list[VisualTag], category: VisualTagCategory) -> str | None:
    candidates = [tag for tag in tags if tag.category == category]
    return max(candidates, key=lambda item: item.confidence).tag if candidates else None


def _average_tag_confidence(tags: list[VisualTag]) -> float:
    return sum(tag.confidence for tag in tags) / len(tags) if tags else 0.0


def _recommended_strategy(results: list[SegmentVisualTagResult]) -> str:
    actions = Counter(
        tag.tag
        for result in results
        for tag in result.tags
        if tag.category == VisualTagCategory.action
    )
    if actions["comparison"] or actions["before_after"] or actions["result_showcase"] >= 2:
        return "sales_recut"
    if actions["testing"] or actions["usage_demo"] >= 3:
        return "product_review_voiceover"
    return "chill_immersive"
