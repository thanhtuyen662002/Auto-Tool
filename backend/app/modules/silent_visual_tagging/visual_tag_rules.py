from __future__ import annotations

from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType
from app.modules.silent_visual_tagging.visual_tag_schema import TAG_CATEGORY_BY_NAME, VisualTag


class VisualTagRules:
    def tags_from_segment_features(
        self,
        segment: SilentVisualSegment,
        segment_index: int,
        total_segments: int,
    ) -> list[VisualTag]:
        tags: list[VisualTag] = []

        if segment_index == 0:
            tags.extend(self._make(["product_reveal", "first_look"], "visual_rule", 0.55, "First segment in timeline"))
        final_window_start = total_segments - 2 if total_segments >= 4 else total_segments - 1
        if total_segments > 0 and segment_index >= final_window_start:
            tags.extend(self._make(["final_result", "cta_scene"], "visual_rule", 0.52, "Near end of timeline"))

        motion = segment.motion_score
        sharpness = segment.sharpness_score
        brightness = segment.brightness_score
        if motion is not None:
            if motion >= 0.58:
                tags.extend(self._make(["usage_demo", "hands_operation", "high_motion", "demo_step"], "visual_rule", 0.55, "High segment motion"))
            elif motion <= 0.25:
                tags.extend(self._make(["low_motion", "stable_shot"], "visual_rule", 0.55, "Low segment motion"))
        if sharpness is not None:
            if sharpness >= 0.62:
                tags.extend(self._make(["clear_frame"], "visual_rule", 0.55, "High frame sharpness"))
                if (motion or 0.0) <= 0.35:
                    tags.extend(self._make(["closeup", "detail_closeup"], "visual_rule", 0.52, "Sharp and low-motion frame"))
            elif sharpness <= 0.28:
                tags.extend(self._make(["blur_risk"], "visual_rule", 0.60, "Low frame sharpness"))
        if brightness is not None and brightness <= 0.28:
            tags.extend(self._make(["dark_frame"], "visual_rule", 0.60, "Low frame brightness"))

        type_tags = {
            VisualSegmentType.unboxing: ["unboxing", "opening_package", "packaging"],
            VisualSegmentType.product_reveal: ["product_reveal", "first_look"],
            VisualSegmentType.closeup: ["closeup", "detail_closeup"],
            VisualSegmentType.demo: ["usage_demo", "testing", "demo_step"],
            VisualSegmentType.usage_scene: ["usage_demo", "benefit_scene"],
            VisualSegmentType.before_after: ["before_after", "comparison"],
            VisualSegmentType.result: ["final_result", "result_showcase"],
        }
        if segment.segment_type in type_tags:
            tags.extend(
                self._make(
                    type_tags[segment.segment_type],
                    "segment_type",
                    0.70,
                    f"Segment type: {segment.segment_type.value}",
                )
            )
        return tags

    @staticmethod
    def _make(tags: list[str], source: str, confidence: float, reason: str) -> list[VisualTag]:
        return [
            VisualTag(
                tag=tag,
                category=TAG_CATEGORY_BY_NAME[tag],
                confidence=confidence,
                source=source,
                reason=reason,
            )
            for tag in tags
        ]
