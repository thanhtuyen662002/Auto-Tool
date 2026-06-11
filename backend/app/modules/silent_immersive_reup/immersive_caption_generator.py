from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.silent_caption_templates import SilentCaptionIntent, SilentCaptionTemplateService
from app.modules.silent_caption_templates.caption_template_service import normalize_industry
from app.modules.silent_immersive_reup.silent_schema import ImmersiveCaptionLine, SilentVisualSegment, VisualSegmentType
from app.modules.subtitle_quality.subtitle_quality_scorer import SubtitleQualityScorer
from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine
from app.modules.silent_visual_tagging.visual_tag_schema import VisualTagCategory


class ImmersiveCaptionGenerator:
    def __init__(
        self,
        template_service: SilentCaptionTemplateService | None = None,
        quality_scorer: SubtitleQualityScorer | None = None,
    ) -> None:
        self.template_service = template_service or SilentCaptionTemplateService()
        self.quality_scorer = quality_scorer or SubtitleQualityScorer()

    def generate_captions(
        self,
        video_path: str,
        segments: list[SilentVisualSegment],
        strategy: str,
        product_context: dict | None = None,
        ocr_translated_srt_path: str | None = None,
        industry: str | None = None,
        tone: str = "natural",
        recent_caption_texts: list[str] | None = None,
        video_recommended_industry: str | None = None,
        use_visual_tags: bool = True,
    ) -> list[ImmersiveCaptionLine]:
        if ocr_translated_srt_path and Path(ocr_translated_srt_path).exists():
            captions = self._captions_from_ocr(ocr_translated_srt_path, video_path)
            scored = self._score_captions(captions)
            if scored and _average_quality(scored) >= 0.7:
                return scored

        if not segments:
            media = probe_video(video_path)
            segments = [
                SilentVisualSegment(
                    id="seg_001",
                    video_path=video_path,
                    start=0,
                    end=media.duration,
                    duration=media.duration,
                    segment_type=VisualSegmentType.product_reveal,
                    visual_score=0.5,
                )
            ]

        selected_industry = industry if industry and industry != "auto" else None
        product_industry = (product_context or {}).get("industry") or (product_context or {}).get("category")
        recent = list(recent_caption_texts or [])
        captions: list[ImmersiveCaptionLine] = []
        for index, segment in enumerate(segments, start=1):
            if segment.duration < 0.35:
                continue
            segment_industry = normalize_industry(
                (segment.primary_industry if use_visual_tags else None)
                or selected_industry
                or video_recommended_industry
                or product_industry
            )
            intent = _intent_for_segment(segment.segment_type, segment if use_visual_tags else None)
            if len(segments) > 1 and index == len(segments):
                intent = SilentCaptionIntent.cta
            caption = self._generate_template_caption(
                index=index,
                segment=segment,
                industry=segment_industry,
                intent=intent,
                strategy=strategy,
                tone=tone,
                product_context=product_context,
                recent=recent,
                selection_reason=_selection_reason(segment, segment_industry, intent, use_visual_tags),
            )
            captions.append(caption)
            recent.append(caption.text)
        return captions

    def _generate_template_caption(
        self,
        *,
        index: int,
        segment: SilentVisualSegment,
        industry: str,
        intent: SilentCaptionIntent,
        strategy: str,
        tone: str,
        product_context: dict | None,
        recent: list[str],
        selection_reason: str,
    ) -> ImmersiveCaptionLine:
        avoid = list(recent)
        best: ImmersiveCaptionLine | None = None
        for _attempt in range(3):
            template = self.template_service.pick_template(
                industry=industry,
                intent=intent.value,
                strategy=strategy,
                product_context=product_context,
                avoid_recent_texts=avoid,
                tone=tone,
            )
            text = self.template_service.render_template(template, product_context)
            source = "template"
            product_name = _product_name(product_context)
            if product_name and intent == SilentCaptionIntent.product_reveal:
                text = _short_caption(f"{product_name}: {text}", max_chars=56)
                source = "visual_generated"
            candidate = ImmersiveCaptionLine(
                index=index,
                start=segment.start,
                end=segment.end,
                text=text,
                source=source,
                segment_id=segment.id,
                template_id=template.id,
                selected_industry=template.industry.value,
                selected_intent=template.intent.value,
                selection_reason=selection_reason,
            )
            scored = self._score_captions([candidate])[0]
            best = scored
            if not scored.quality_needs_review:
                return scored
            avoid.append(text)
        return best or candidate

    def _score_captions(self, captions: list[ImmersiveCaptionLine]) -> list[ImmersiveCaptionLine]:
        lines = [
            SubtitleLine(
                index=caption.index,
                start_ms=round(caption.start * 1000),
                end_ms=round(caption.end * 1000),
                source_text=None,
                translated_text=caption.text,
            )
            for caption in captions
        ]
        result: list[ImmersiveCaptionLine] = []
        for index, (caption, line) in enumerate(zip(captions, lines)):
            score = self.quality_scorer.score_line(
                line,
                previous_line=lines[index - 1] if index > 0 else None,
                next_line=lines[index + 1] if index + 1 < len(lines) else None,
                source_type=caption.source,
            )
            result.append(
                caption.model_copy(
                    update={
                        "quality_score": score.score,
                        "quality_needs_review": score.needs_review,
                        "quality_issues": [issue.issue_type.value for issue in score.issues],
                        "warnings": [*caption.warnings, *[issue.message for issue in score.issues]],
                    }
                )
            )
        return result

    @staticmethod
    def _captions_from_ocr(path: str, video_path: str) -> list[ImmersiveCaptionLine]:
        captions: list[ImmersiveCaptionLine] = []
        try:
            blocks = parse_srt_blocks(path)
        except Exception:
            return []
        for index, block in enumerate(blocks, start=1):
            captions.append(
                ImmersiveCaptionLine(
                    index=index,
                    start=block.start,
                    end=block.end,
                    text=_short_caption(block.text),
                    source="ocr_translation",
                )
            )
        return captions


def _intent_for_segment(
    segment_type: VisualSegmentType,
    segment: SilentVisualSegment | None = None,
) -> SilentCaptionIntent:
    action = (segment.primary_action or "") if segment else ""
    tag_names = {tag.tag for tag in (segment.visual_tags if segment else [])}
    action_mapping = {
        "unboxing": SilentCaptionIntent.unboxing,
        "opening_package": SilentCaptionIntent.unboxing,
        "closeup": SilentCaptionIntent.closeup,
        "usage_demo": SilentCaptionIntent.demo,
        "testing": SilentCaptionIntent.demo,
        "organizing": SilentCaptionIntent.demo,
        "cleaning": SilentCaptionIntent.demo,
        "wiping": SilentCaptionIntent.demo,
        "final_result": SilentCaptionIntent.result,
        "result_showcase": SilentCaptionIntent.result,
        "before_after": SilentCaptionIntent.result,
        "product_reveal": SilentCaptionIntent.product_reveal,
    }
    if action in action_mapping:
        return action_mapping[action]
    for tag in (
        "unboxing",
        "opening_package",
        "closeup",
        "usage_demo",
        "testing",
        "organizing",
        "cleaning",
        "wiping",
        "result_showcase",
        "before_after",
        "product_reveal",
    ):
        if tag in tag_names:
            return action_mapping[tag]
    if "detail_closeup" in tag_names:
        return SilentCaptionIntent.closeup
    if "benefit_scene" in tag_names:
        return SilentCaptionIntent.benefit
    if "cta_scene" in tag_names:
        return SilentCaptionIntent.cta
    mapping = {
        VisualSegmentType.product_reveal: SilentCaptionIntent.product_reveal,
        VisualSegmentType.unboxing: SilentCaptionIntent.unboxing,
        VisualSegmentType.closeup: SilentCaptionIntent.closeup,
        VisualSegmentType.demo: SilentCaptionIntent.demo,
        VisualSegmentType.before_after: SilentCaptionIntent.result,
        VisualSegmentType.usage_scene: SilentCaptionIntent.benefit,
        VisualSegmentType.result: SilentCaptionIntent.result,
        VisualSegmentType.transition: SilentCaptionIntent.hook,
        VisualSegmentType.unknown: SilentCaptionIntent.benefit,
    }
    return mapping.get(segment_type, SilentCaptionIntent.hook)


def _selection_reason(
    segment: SilentVisualSegment,
    industry: str,
    intent: SilentCaptionIntent,
    use_visual_tags: bool,
) -> str:
    sources = sorted({tag.source for tag in segment.visual_tags}) if use_visual_tags else []
    suffix = f"; tag sources: {', '.join(sources)}" if sources else ""
    return f"Caption picked from: {industry} + {intent.value}{suffix}"


def _product_name(product_context: dict | None) -> str:
    if not product_context:
        return ""
    return str(product_context.get("product_name") or product_context.get("name") or "").strip()


def _first_feature(product_context: dict | None) -> str:
    if not product_context:
        return ""
    features = product_context.get("features") or []
    if isinstance(features, str):
        features = [line.strip() for line in features.splitlines() if line.strip()]
    if not isinstance(features, list) or not features:
        return ""
    return str(features[0]).strip()


def _cta(product_context: dict | None) -> str:
    if not product_context:
        return ""
    return str(product_context.get("cta") or "").strip()


def _short_caption(text: str, max_chars: int = 52) -> str:
    cleaned = " ".join(text.replace("\n", " ").split())
    if len(cleaned) <= max_chars:
        return cleaned
    words = cleaned.split()
    result: list[str] = []
    for word in words:
        candidate = " ".join([*result, word])
        if len(candidate) > max_chars:
            break
        result.append(word)
    return " ".join(result) or cleaned[:max_chars].rstrip()


def _average_quality(captions: list[ImmersiveCaptionLine]) -> float:
    scores = [caption.quality_score for caption in captions if caption.quality_score is not None]
    return sum(scores) / len(scores) if scores else 1.0
