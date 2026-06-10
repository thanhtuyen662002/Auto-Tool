from __future__ import annotations

from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment, VisualSegmentType


class ImmersiveSceneClassifier:
    def classify_segments(
        self,
        segments: list[SilentVisualSegment],
        product_context: dict | None = None,
    ) -> list[SilentVisualSegment]:
        if not segments:
            return []
        total = len(segments)
        classified: list[SilentVisualSegment] = []
        for index, segment in enumerate(segments):
            segment_type = self._classify_one(segment, index=index, total=total)
            classified.append(segment.model_copy(update={"segment_type": segment_type}))
        return classified

    @staticmethod
    def _classify_one(segment: SilentVisualSegment, *, index: int, total: int) -> VisualSegmentType:
        text = (segment.ocr_text or "").lower()
        keyword_map = {
            "开箱": VisualSegmentType.unboxing,
            "测评": VisualSegmentType.demo,
            "推荐": VisualSegmentType.product_reveal,
            "使用": VisualSegmentType.usage_scene,
            "效果": VisualSegmentType.result,
            "收纳": VisualSegmentType.usage_scene,
            "对比": VisualSegmentType.before_after,
        }
        for keyword, segment_type in keyword_map.items():
            if keyword in text:
                return segment_type

        motion = segment.motion_score or 0.0
        sharpness = segment.sharpness_score or 0.0
        if index == 0:
            return VisualSegmentType.product_reveal
        if motion >= 0.58:
            return VisualSegmentType.demo
        if sharpness >= 0.62 and motion <= 0.35:
            return VisualSegmentType.closeup
        if index >= max(0, total - 2):
            return VisualSegmentType.result if motion < 0.35 else VisualSegmentType.usage_scene
        return VisualSegmentType.usage_scene
