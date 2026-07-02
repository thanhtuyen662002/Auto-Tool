from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.adapters.gemini_adapter import GeminiAdapter, ScriptGenerationError
from app.modules.silent_immersive_reup.silent_schema import (
    ProductDetectionCandidate,
    ProductDetectionEvidence,
    ProductDetectionFrameObservation,
    SilentProductDetectionReport,
    SilentVisualSegment,
)
from app.modules.silent_visual_tagging.visual_tag_schema import VideoVisualTagReport, VisualTagCategory


DEFAULT_PRODUCT_VISION_MODEL = "gemini-3.1-flash-lite"


@dataclass(frozen=True)
class DetectionFrameAsset:
    label: str
    frame_path: str
    crop_path: str | None = None
    segment_id: str | None = None
    visual_score: float = 0.0

    def image_paths(self) -> list[str]:
        return [self.frame_path, *([self.crop_path] if self.crop_path else [])]


class ProductVisionClient(Protocol):
    def generate_json_with_images(self, prompt: str, image_paths: list[str]) -> dict:
        ...


class SilentProductDetector:
    def __init__(
        self,
        vision_client: ProductVisionClient | None = None,
        model_name: str = DEFAULT_PRODUCT_VISION_MODEL,
        frame_limit: int = 6,
        min_context_confidence: float = 0.58,
    ) -> None:
        self.vision_client = vision_client
        self.model_name = model_name
        self.frame_limit = max(1, min(10, int(frame_limit)))
        self.min_context_confidence = max(0.0, min(1.0, float(min_context_confidence)))

    def detect(
        self,
        *,
        video_path: str,
        segments: list[SilentVisualSegment],
        visual_tag_report: VideoVisualTagReport | None = None,
        product_context: dict | None = None,
        gemini_api_keys: list[str] | None = None,
    ) -> SilentProductDetectionReport:
        if _product_lock_enabled(product_context) and _manual_product_label(product_context):
            return self._manual_report(video_path, product_context or {})

        frame_assets = _select_representative_frame_assets(segments, self.frame_limit)
        frame_paths = [asset.frame_path for asset in frame_assets]
        focus_crop_paths = [asset.crop_path for asset in frame_assets if asset.crop_path]
        vision_image_paths = [path for asset in frame_assets for path in asset.image_paths()]
        warnings: list[str] = []
        if vision_image_paths and gemini_api_keys:
            try:
                client = self.vision_client or GeminiAdapter(
                    api_key=None,
                    api_keys=gemini_api_keys,
                    model_name=self.model_name,
                    timeout_seconds=45,
                )
                payload = client.generate_json_with_images(
                    _vision_prompt(
                        video_path=video_path,
                        segments=segments,
                        frame_assets=frame_assets,
                        visual_tag_report=visual_tag_report,
                        product_context=product_context,
                    ),
                    vision_image_paths,
                )
                report = self._report_from_vision_payload(video_path, frame_assets, payload)
                if report.top_candidate and report.top_candidate.certainty != "unknown":
                    return report
                warnings.extend(report.warnings)
            except (ScriptGenerationError, OSError, ValueError, KeyError, TypeError) as exc:
                warnings.append(f"AI vision không nhận diện được sản phẩm: {exc}")

        if vision_image_paths and not gemini_api_keys:
            warnings.append("Chua co Gemini API key nen AI vision chua chay; tool tam dung nhan dien heuristic.")

        fallback = self._fallback_report(
            video_path=video_path,
            segments=segments,
            visual_tag_report=visual_tag_report,
            frame_paths=frame_paths,
            focus_crop_paths=focus_crop_paths,
        )
        if not frame_paths:
            fallback.warnings.append("Không có frame đại diện đủ rõ để gửi nhận diện sản phẩm.")
        fallback.warnings.extend(warnings)
        return fallback

    def _report_from_vision_payload(
        self,
        video_path: str,
        frame_assets: list[DetectionFrameAsset],
        payload: dict,
    ) -> SilentProductDetectionReport:
        frame_paths = [asset.frame_path for asset in frame_assets]
        focus_crop_paths = [asset.crop_path for asset in frame_assets if asset.crop_path]
        frame_observations = _frame_observations_from_payload(payload, frame_assets)
        raw_candidates = payload.get("candidates") or [payload]
        if not isinstance(raw_candidates, list):
            raw_candidates = [payload]
        candidates = [
            _candidate_from_payload(item, frame_paths)
            for item in raw_candidates
            if isinstance(item, dict)
        ]
        candidates = _merge_observation_candidates(candidates, frame_observations)
        candidates = [candidate for candidate in candidates if candidate.display_name.strip()]
        candidates = _stabilize_candidates(candidates, frame_observations)
        candidates.sort(key=lambda item: item.confidence, reverse=True)
        top = candidates[0] if candidates else None
        confidence = top.confidence if top else 0.0
        warnings = _clean_list(payload.get("warnings"))
        if top and "ambiguous_product_detection" in top.risk_flags:
            warnings.append("AI vision thấy nhiều vật thể sản phẩm có điểm gần nhau; cần khóa sản phẩm trước khi tạo voice/sub.")
        if top and "single_frame_evidence" in top.risk_flags:
            warnings.append("AI vision chỉ có bằng chứng mạnh ở một frame; không nên tự tạo voice/sub nếu không có OCR hoặc sản phẩm khóa tay.")
        if top and top.product_name and top.certainty != "exact_product":
            top = top.model_copy(update={"product_name": ""})
            candidates[0] = top
            warnings.append("AI có nhắc tên sản phẩm nhưng chưa đủ chắc SKU/brand nên chỉ dùng như loại sản phẩm.")
        return SilentProductDetectionReport(
            video_path=video_path,
            provider="gemini_vision",
            model=self.model_name,
            status="detected" if top and confidence >= 0.35 else "unavailable",
            top_candidate=top,
            candidates=candidates,
            frame_observations=frame_observations,
            context_updates=context_updates_from_detection(top, self.min_context_confidence),
            frame_paths=frame_paths,
            focus_crop_paths=focus_crop_paths,
            average_confidence=round(confidence, 4),
            warnings=warnings,
            created_at=_now(),
        )

    def _fallback_report(
        self,
        *,
        video_path: str,
        segments: list[SilentVisualSegment],
        visual_tag_report: VideoVisualTagReport | None,
        frame_paths: list[str],
        focus_crop_paths: list[str],
    ) -> SilentProductDetectionReport:
        industry = (visual_tag_report.recommended_industry if visual_tag_report else None) or _primary_industry_from_segments(segments)
        industry = industry or "general_product"
        actions = _top_tags(visual_tag_report, VisualTagCategory.action)
        scenes = _top_tags(visual_tag_report, VisualTagCategory.scene)
        product_type = _fallback_product_type(industry, actions, scenes)
        confidence = _fallback_confidence(visual_tag_report, segments)
        evidence = [
            ProductDetectionEvidence(
                source="visual_tag",
                value=f"{tag}:{count}",
                confidence=min(0.55, confidence),
            )
            for tag, count in [*actions[:3], *scenes[:2]]
        ]
        for segment in sorted(segments, key=lambda item: item.visual_score, reverse=True)[:2]:
            if segment.representative_frame_path:
                evidence.append(
                    ProductDetectionEvidence(
                        source="frame",
                        value=f"{segment.id} frame_score={segment.visual_score:.2f}",
                        confidence=min(0.5, segment.visual_score),
                        segment_id=segment.id,
                        frame_path=segment.representative_frame_path,
                    )
                )
        certainty = "category_only" if confidence < self.min_context_confidence else "product_type"
        candidate = ProductDetectionCandidate(
            display_name=product_type,
            product_type=product_type if certainty == "product_type" else "",
            industry=industry,
            certainty=certainty,
            confidence=round(confidence, 4),
            visible_features=_fallback_features(actions, scenes),
            use_cases=_fallback_use_cases(industry, actions),
            evidence=evidence,
            risk_flags=["no_ai_vision"] if certainty == "category_only" else [],
        )
        return SilentProductDetectionReport(
            video_path=video_path,
            provider="heuristic_fallback",
            model=None,
            status="fallback",
            top_candidate=candidate,
            candidates=[candidate],
            frame_observations=[],
            context_updates=context_updates_from_detection(candidate, self.min_context_confidence),
            frame_paths=frame_paths,
            focus_crop_paths=focus_crop_paths,
            average_confidence=candidate.confidence,
            warnings=[
                "Chưa có kết quả AI vision; tool chỉ dùng visual tags/frame score nên không khẳng định chính xác sản phẩm."
            ],
            created_at=_now(),
        )

    def _manual_report(self, video_path: str, product_context: dict) -> SilentProductDetectionReport:
        label = _manual_product_label(product_context)
        industry = str(product_context.get("industry") or product_context.get("category") or "general_product").strip() or "general_product"
        features = _clean_list(product_context.get("features") or product_context.get("locked_product_keywords"))
        candidate = ProductDetectionCandidate(
            display_name=label,
            product_name=label,
            product_type=label,
            industry=industry,
            certainty="exact_product",
            confidence=1.0,
            visible_features=features,
            use_cases=[],
            evidence=[
                ProductDetectionEvidence(
                    source="manual",
                    value="Người dùng đã khóa ngữ cảnh sản phẩm.",
                    confidence=1.0,
                )
            ],
        )
        return SilentProductDetectionReport(
            video_path=video_path,
            provider="manual_context",
            model=None,
            status="manual_context",
            top_candidate=candidate,
            candidates=[candidate],
            frame_observations=[],
            context_updates=context_updates_from_detection(candidate, self.min_context_confidence),
            frame_paths=[],
            focus_crop_paths=[],
            average_confidence=1.0,
            warnings=[],
            created_at=_now(),
        )


def merge_product_detection_context(
    product_context: dict | None,
    report: SilentProductDetectionReport | None,
) -> dict:
    context = dict(product_context or {})
    if _product_lock_enabled(context):
        return context
    if report and report.context_updates:
        context.update(report.context_updates)
    return context


def context_updates_from_detection(
    candidate: ProductDetectionCandidate | None,
    min_confidence: float = 0.58,
) -> dict[str, object]:
    if candidate is None or candidate.certainty == "unknown":
        return {}
    updates: dict[str, object] = {
        "industry": candidate.industry,
        "category": candidate.industry,
        "auto_detected_product": True,
        "product_detection_confidence": candidate.confidence,
        "product_detection_certainty": candidate.certainty,
    }
    features = _dedupe([*candidate.visible_features, *candidate.use_cases])
    if features:
        updates["features"] = features[:5]
    unstable_detection = any(
        flag in {"single_frame_evidence", "ambiguous_product_detection"}
        for flag in candidate.risk_flags
    )
    if (
        candidate.confidence >= min_confidence
        and candidate.certainty in {"exact_product", "product_type"}
        and not unstable_detection
    ):
        label = candidate.product_name or candidate.product_type or candidate.display_name
        if label:
            updates["product_name"] = label
            updates["name"] = label
    return updates


def _vision_prompt(
    *,
    video_path: str,
    segments: list[SilentVisualSegment],
    frame_assets: list[DetectionFrameAsset],
    visual_tag_report: VideoVisualTagReport | None,
    product_context: dict | None,
) -> str:
    segment_summary = [
        {
            "id": segment.id,
            "time": f"{segment.start:.1f}-{segment.end:.1f}s",
            "type": segment.segment_type.value if hasattr(segment.segment_type, "value") else str(segment.segment_type),
            "visual_score": segment.visual_score,
            "tags": [tag.tag for tag in segment.visual_tags[:6]],
        }
        for segment in segments[:10]
    ]
    frame_summary = [
        {
            "label": asset.label,
            "segment_id": asset.segment_id,
            "full_frame": Path(asset.frame_path).name,
            "focus_crop": Path(asset.crop_path).name if asset.crop_path else None,
            "visual_score": round(asset.visual_score, 4),
        }
        for asset in frame_assets
    ]
    context = product_context or {}
    return (
        "Bạn là bộ nhận diện sản phẩm chính cho video affiliate Douyin không thoại. "
        "Mỗi frame có thể có ảnh gốc và focus crop; focus crop thường là vùng sản phẩm chính đã được tool tách để giảm nhiễu. "
        "Hãy nhận diện từng frame/crop riêng, sau đó vote sản phẩm chính xuất hiện lặp lại nhiều nhất. "
        "Ưu tiên vật thể được tay thao tác, xuất hiện ở cận cảnh/crop, lặp lại qua nhiều frame. "
        "Giảm trọng số đồ nền, tay, bàn, hộp, chữ watermark, logo nền tảng, vật thể chỉ xuất hiện thoáng qua. "
        "Không được bịa brand, model, SKU, chất liệu, giá hoặc tính năng nếu không nhìn thấy rõ. "
        "Nếu chỉ chắc loại sản phẩm, đặt product_name rỗng, product_type là loại sản phẩm tiếng Việt. "
        "Nếu chỉ chắc ngành hàng, certainty='category_only'. "
        "Các industry hợp lệ: home_goods, kitchen_goods, desk_setup, storage_organization, beauty_goods, cleaning_goods, dorm_goods, general_product. "
        "JSON thuần dạng: {\"frame_observations\":[{\"frame_label\":\"frame_001\",\"product_type\":\"...\",\"industry\":\"...\","
        "\"primary_object\":\"...\",\"is_product_visible\":true,\"confidence\":0.0,\"visible_features\":[\"...\"],"
        "\"evidence\":\"focus crop cho thấy ...\",\"noise_objects\":[\"tay\",\"bàn\"]}],"
        "\"candidates\":[{\"display_name\":\"...\",\"product_name\":\"\",\"product_type\":\"...\","
        "\"industry\":\"...\",\"certainty\":\"product_type|category_only|exact_product|unknown\",\"confidence\":0.0,"
        "\"visible_features\":[\"...\"],\"use_cases\":[\"...\"],\"evidence\":[{\"source\":\"frame\","
        "\"value\":\"frame_001/focus crop cho thấy ...\",\"confidence\":0.0}],\"risk_flags\":[\"...\"]}],\"warnings\":[\"...\"]}. "
        f"Video: {Path(video_path).name}. "
        f"Frame/crop mapping: {json.dumps(frame_summary, ensure_ascii=False)}. "
        f"Visual tags gợi ý: {json.dumps((visual_tag_report.model_dump(mode='json') if visual_tag_report else {}), ensure_ascii=False)[:1800]}. "
        f"Segments: {json.dumps(segment_summary, ensure_ascii=False)}. "
        f"Ngữ cảnh người dùng nếu có: {json.dumps(context, ensure_ascii=False)[:1000]}."
    )
    return (
        "Bạn là bộ nhận diện sản phẩm cho video affiliate Douyin không thoại. "
        "Hãy nhìn các frame đại diện theo thứ tự thời gian và trả JSON thuần. "
        "Không được bịa brand, model, SKU, chất liệu, giá hoặc tính năng nếu không nhìn thấy rõ. "
        "Nếu chỉ chắc loại sản phẩm, đặt product_name rỗng, product_type là loại sản phẩm tiếng Việt. "
        "Nếu chỉ chắc ngành hàng, certainty='category_only'. "
        "Các industry hợp lệ: home_goods, kitchen_goods, desk_setup, storage_organization, beauty_goods, cleaning_goods, dorm_goods, general_product. "
        "JSON dạng: {\"candidates\":[{\"display_name\":\"...\",\"product_name\":\"\",\"product_type\":\"...\","
        "\"industry\":\"...\",\"certainty\":\"product_type|category_only|exact_product|unknown\",\"confidence\":0.0,"
        "\"visible_features\":[\"...\"],\"use_cases\":[\"...\"],\"evidence\":[{\"source\":\"frame\","
        "\"value\":\"Frame 1 cho thấy ...\",\"confidence\":0.0}],\"risk_flags\":[\"...\"]}],\"warnings\":[\"...\"]}. "
        f"Video: {Path(video_path).name}. "
        f"Visual tags gợi ý: {json.dumps((visual_tag_report.model_dump(mode='json') if visual_tag_report else {}), ensure_ascii=False)[:1800]}. "
        f"Segments: {json.dumps(segment_summary, ensure_ascii=False)}. "
        f"Ngữ cảnh người dùng nếu có: {json.dumps(context, ensure_ascii=False)[:1000]}."
    )


def _frame_observations_from_payload(
    payload: dict[str, Any],
    frame_assets: list[DetectionFrameAsset],
) -> list[ProductDetectionFrameObservation]:
    raw_observations = payload.get("frame_observations") or payload.get("frames") or []
    if not isinstance(raw_observations, list):
        return []
    assets_by_label = {asset.label: asset for asset in frame_assets}
    observations: list[ProductDetectionFrameObservation] = []
    for index, item in enumerate(raw_observations, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("frame_label") or item.get("label") or f"frame_{index:03d}").strip()
        asset = assets_by_label.get(label)
        observations.append(
            ProductDetectionFrameObservation(
                frame_label=label,
                frame_path=asset.frame_path if asset else None,
                crop_path=asset.crop_path if asset else None,
                product_type=_clean_text(item.get("product_type") or item.get("type")),
                industry=_normalize_industry(item.get("industry") or item.get("category")),
                primary_object=_clean_text(item.get("primary_object") or item.get("object")),
                is_product_visible=_bool(item.get("is_product_visible"), True),
                confidence=_float01(item.get("confidence"), 0.0),
                visible_features=_clean_list(item.get("visible_features") or item.get("features")),
                evidence=_clean_text(item.get("evidence") or item.get("reason")),
                noise_objects=_clean_list(item.get("noise_objects") or item.get("background_objects")),
            )
        )
    return observations


def _merge_observation_candidates(
    candidates: list[ProductDetectionCandidate],
    observations: list[ProductDetectionFrameObservation],
) -> list[ProductDetectionCandidate]:
    observation_candidates = _candidates_from_observation_vote(observations)
    if not observation_candidates:
        return candidates
    if not candidates:
        return observation_candidates

    merged: list[ProductDetectionCandidate] = list(candidates)
    for voted in observation_candidates:
        voted_key = _canonical_product_label(voted.product_type or voted.display_name)
        matched_index = next(
            (
                index
                for index, candidate in enumerate(merged)
                if _canonical_product_label(candidate.product_type or candidate.display_name) == voted_key
            ),
            None,
        )
        if matched_index is None:
            merged.append(voted)
            continue
        current = merged[matched_index]
        merged[matched_index] = current.model_copy(
            update={
                "confidence": round(max(current.confidence, voted.confidence), 4),
                "visible_features": _dedupe([*current.visible_features, *voted.visible_features])[:8],
                "use_cases": _dedupe([*current.use_cases, *voted.use_cases])[:8],
                "evidence": [*current.evidence, *voted.evidence][:10],
                "risk_flags": _dedupe([*current.risk_flags, *voted.risk_flags]),
            }
        )
    return merged


def _candidates_from_observation_vote(
    observations: list[ProductDetectionFrameObservation],
) -> list[ProductDetectionCandidate]:
    groups: dict[str, list[ProductDetectionFrameObservation]] = {}
    for observation in observations:
        if not observation.is_product_visible or observation.confidence < 0.2:
            continue
        label = observation.product_type or observation.primary_object
        key = _canonical_product_label(label)
        if not key or key in {"tay", "ban", "mat ban", "hop", "nen"}:
            continue
        groups.setdefault(key, []).append(observation)

    candidates: list[ProductDetectionCandidate] = []
    for observations_for_label in groups.values():
        label = _most_common_clean([item.product_type or item.primary_object for item in observations_for_label])
        industry = _most_common_clean([item.industry for item in observations_for_label]) or "general_product"
        support = len(observations_for_label)
        average = sum(item.confidence for item in observations_for_label) / support
        crop_bonus = 0.05 if any(item.crop_path for item in observations_for_label) else 0.0
        support_bonus = min(0.18, max(0, support - 1) * 0.055)
        confidence = round(min(0.97, average + crop_bonus + support_bonus), 4)
        certainty = "product_type" if confidence >= 0.56 and label else "category_only"
        evidence = [
            ProductDetectionEvidence(
                source="frame",
                value=item.evidence or f"{item.frame_label}: {label}",
                confidence=item.confidence,
                frame_path=item.crop_path or item.frame_path,
            )
            for item in observations_for_label[:6]
        ]
        candidates.append(
            ProductDetectionCandidate(
                display_name=label or _fallback_product_type(industry, [], []),
                product_type=label if certainty == "product_type" else "",
                industry=_normalize_industry(industry),
                certainty=certainty,
                confidence=confidence,
                visible_features=_dedupe(feature for item in observations_for_label for feature in item.visible_features)[:8],
                use_cases=_fallback_use_cases(_normalize_industry(industry), []),
                evidence=evidence,
                risk_flags=[] if support >= 2 else ["single_frame_evidence"],
            )
        )
    return sorted(candidates, key=lambda item: (-item.confidence, item.display_name))


def _stabilize_candidates(
    candidates: list[ProductDetectionCandidate],
    observations: list[ProductDetectionFrameObservation],
) -> list[ProductDetectionCandidate]:
    if not candidates:
        return []
    support_by_key: Counter[str] = Counter()
    for observation in observations:
        if not observation.is_product_visible or observation.confidence < 0.2:
            continue
        key = _canonical_product_label(observation.product_type or observation.primary_object)
        if key:
            support_by_key[key] += 1

    stabilized: list[ProductDetectionCandidate] = []
    for candidate in candidates:
        key = _canonical_product_label(candidate.product_type or candidate.display_name)
        support = max(int(support_by_key.get(key, 0)), _candidate_evidence_support(candidate))
        risk_flags = _dedupe(candidate.risk_flags)
        confidence = float(candidate.confidence or 0.0)
        if candidate.certainty != "exact_product" and support <= 1:
            confidence = min(confidence, 0.62)
            if "single_frame_evidence" not in risk_flags:
                risk_flags.append("single_frame_evidence")
        stabilized.append(candidate.model_copy(update={"confidence": round(confidence, 4), "risk_flags": risk_flags}))

    sorted_candidates = sorted(stabilized, key=lambda item: item.confidence, reverse=True)
    if len(sorted_candidates) >= 2:
        top = sorted_candidates[0]
        second = sorted_candidates[1]
        top_key = _canonical_product_label(top.product_type or top.display_name)
        second_key = _canonical_product_label(second.product_type or second.display_name)
        if (
            top.certainty != "exact_product"
            and second.certainty != "unknown"
            and top_key
            and second_key
            and top_key != second_key
            and float(top.confidence) - float(second.confidence) < 0.08
        ):
            sorted_candidates[0] = top.model_copy(
                update={
                    "confidence": round(min(float(top.confidence), 0.7), 4),
                    "risk_flags": _dedupe([*top.risk_flags, "ambiguous_product_detection"]),
                }
            )
    return sorted_candidates


def _candidate_evidence_support(candidate: ProductDetectionCandidate) -> int:
    markers: set[str] = set()
    for evidence in candidate.evidence:
        if evidence.frame_path:
            markers.add(str(evidence.frame_path))
            continue
        if evidence.segment_id:
            markers.add(str(evidence.segment_id))
            continue
        value = str(evidence.value or "")
        frame_labels = re.findall(r"frame[_\s-]?(\d{1,4})", value, flags=re.IGNORECASE)
        if frame_labels:
            markers.update(frame_labels)
        elif value.strip():
            markers.add(value.strip()[:80])
    return len(markers)


def _candidate_from_payload(payload: dict[str, Any], frame_paths: list[str]) -> ProductDetectionCandidate:
    raw_evidence = payload.get("evidence") or []
    evidence: list[ProductDetectionEvidence] = []
    if isinstance(raw_evidence, list):
        for item in raw_evidence[:8]:
            if isinstance(item, dict):
                source = str(item.get("source") or "frame")
                if source not in {"frame", "visual_tag", "ocr_text", "filename", "folder_name", "manual", "heuristic"}:
                    source = "frame"
                evidence.append(
                    ProductDetectionEvidence(
                        source=source,
                        value=str(item.get("value") or item.get("observation") or "").strip()[:240],
                        confidence=_float01(item.get("confidence"), 0.5),
                        segment_id=str(item.get("segment_id") or "").strip() or None,
                        frame_path=str(item.get("frame_path") or "").strip() or None,
                    )
                )
            elif str(item).strip():
                evidence.append(ProductDetectionEvidence(source="frame", value=str(item).strip()[:240], confidence=0.5))
    if not evidence and frame_paths:
        evidence = [
            ProductDetectionEvidence(source="frame", value=f"Frame {index}", confidence=0.45, frame_path=path)
            for index, path in enumerate(frame_paths[:3], start=1)
        ]
    certainty = str(payload.get("certainty") or "unknown").strip()
    if certainty not in {"exact_product", "product_type", "category_only", "unknown"}:
        certainty = "unknown"
    product_name = _clean_text(payload.get("product_name") or payload.get("name"))
    product_type = _clean_text(payload.get("product_type") or payload.get("type"))
    display_name = _clean_text(payload.get("display_name") or product_name or product_type or payload.get("category"))
    industry = _normalize_industry(payload.get("industry") or payload.get("category"))
    return ProductDetectionCandidate(
        display_name=display_name,
        product_name=product_name,
        product_type=product_type,
        industry=industry,
        certainty=certainty,
        confidence=_float01(payload.get("confidence"), 0.0),
        visible_features=_clean_list(payload.get("visible_features") or payload.get("features")),
        use_cases=_clean_list(payload.get("use_cases") or payload.get("benefits")),
        evidence=evidence,
        risk_flags=_clean_list(payload.get("risk_flags")),
    )


def _select_representative_frame_assets(segments: list[SilentVisualSegment], limit: int) -> list[DetectionFrameAsset]:
    candidates = [
        segment
        for segment in segments
        if segment.representative_frame_path and Path(segment.representative_frame_path).exists()
    ]
    if not candidates:
        return []
    first = candidates[:1]
    scored = sorted(candidates[1:], key=lambda item: (item.visual_score, item.sharpness_score or 0, -(item.motion_score or 0)), reverse=True)
    selected: list[SilentVisualSegment] = []
    for segment in [*first, *scored]:
        if segment not in selected:
            selected.append(segment)
        if len(selected) >= limit:
            break
    assets: list[DetectionFrameAsset] = []
    for index, segment in enumerate(selected, start=1):
        frame_path = str(segment.representative_frame_path)
        assets.append(
            DetectionFrameAsset(
                label=f"frame_{index:03d}",
                frame_path=frame_path,
                crop_path=_make_focus_crop(frame_path),
                segment_id=segment.id,
                visual_score=segment.visual_score,
            )
        )
    return assets


def _make_focus_crop(frame_path: str) -> str | None:
    path = Path(frame_path)
    crop_path = path.with_name(f"{path.stem}_product_crop{path.suffix or '.jpg'}")
    if crop_path.exists() and crop_path.stat().st_size > 0:
        return str(crop_path)
    if _make_cv2_focus_crop(path, crop_path):
        return str(crop_path)
    if _make_center_focus_crop(path, crop_path):
        return str(crop_path)
    return None


def _make_cv2_focus_crop(source: Path, target: Path) -> bool:
    try:
        import cv2
        import numpy as np
    except Exception:
        return False
    image = _read_cv2_image(source)
    if image is None:
        return False
    height, width = image.shape[:2]
    if width < 80 or height < 80:
        return False
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 120)
        kernel = np.ones((7, 7), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: list[tuple[float, int, int, int, int]] = []
        center_x = width / 2
        center_y = height / 2
        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            area = box_width * box_height
            if area < width * height * 0.015 or area > width * height * 0.88:
                continue
            box_center_x = x + box_width / 2
            box_center_y = y + box_height / 2
            center_distance = ((box_center_x - center_x) / width) ** 2 + ((box_center_y - center_y) / height) ** 2
            score = area / (width * height) - center_distance * 0.22
            boxes.append((score, x, y, box_width, box_height))
        if not boxes:
            return False
        boxes.sort(reverse=True)
        _score, x, y, box_width, box_height = boxes[0]
        padding_x = int(box_width * 0.22)
        padding_y = int(box_height * 0.22)
        x1 = max(0, x - padding_x)
        y1 = max(0, y - padding_y)
        x2 = min(width, x + box_width + padding_x)
        y2 = min(height, y + box_height + padding_y)
        if (x2 - x1) < width * 0.22 or (y2 - y1) < height * 0.18:
            return False
        crop = image[y1:y2, x1:x2]
        return _write_cv2_image(target, crop)
    except Exception:
        return False


def _make_center_focus_crop(source: Path, target: Path) -> bool:
    try:
        from PIL import Image
    except Exception:
        return False
    try:
        with Image.open(source) as image:
            width, height = image.size
            if width < 80 or height < 80:
                return False
            crop_width = int(width * 0.74)
            crop_height = int(height * 0.72)
            left = max(0, (width - crop_width) // 2)
            top = max(0, (height - crop_height) // 2)
            image.crop((left, top, left + crop_width, top + crop_height)).save(target, quality=92)
        return target.exists() and target.stat().st_size > 0
    except Exception:
        return False


def _read_cv2_image(source: Path):
    try:
        import cv2
        import numpy as np
    except Exception:
        return None
    try:
        data = np.frombuffer(source.read_bytes(), dtype=np.uint8)
        if data.size <= 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _write_cv2_image(target: Path, image) -> bool:
    try:
        import cv2
    except Exception:
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not ok:
            return False
        target.write_bytes(encoded.tobytes())
        return target.exists() and target.stat().st_size > 0
    except Exception:
        return False


def _top_tags(report: VideoVisualTagReport | None, category: VisualTagCategory) -> list[tuple[str, int]]:
    if not report:
        return []
    counter: Counter[str] = Counter()
    for result in report.segment_results:
        for tag in result.tags:
            if tag.category == category:
                counter[tag.tag] += 1
    return counter.most_common(5)


def _primary_industry_from_segments(segments: list[SilentVisualSegment]) -> str | None:
    counter = Counter(segment.primary_industry for segment in segments if segment.primary_industry)
    return counter.most_common(1)[0][0] if counter else None


def _fallback_product_type(industry: str, actions: list[tuple[str, int]], scenes: list[tuple[str, int]]) -> str:
    action_names = {name for name, _count in actions}
    if industry == "cleaning_goods" or {"cleaning", "wiping"} & action_names:
        return "dụng cụ vệ sinh"
    if industry == "storage_organization" or "organizing" in action_names:
        return "đồ sắp xếp/lưu trữ"
    if industry == "kitchen_goods":
        return "đồ dùng nhà bếp"
    if industry == "beauty_goods":
        return "sản phẩm làm đẹp"
    if industry == "desk_setup":
        return "phụ kiện bàn làm việc"
    if industry == "dorm_goods":
        return "đồ dùng phòng nhỏ"
    if industry == "home_goods":
        return "đồ gia dụng"
    if any(name == "kitchen_scene" for name, _count in scenes):
        return "đồ dùng nhà bếp"
    return "sản phẩm trong video"


def _fallback_features(actions: list[tuple[str, int]], scenes: list[tuple[str, int]]) -> list[str]:
    labels = {
        "closeup": "có cảnh quay cận chi tiết",
        "usage_demo": "có cảnh thao tác sử dụng",
        "testing": "có cảnh thử hiệu quả",
        "comparison": "có cảnh so sánh",
        "before_after": "có cảnh trước và sau",
        "organizing": "nhấn vào khả năng sắp xếp gọn",
        "cleaning": "nhấn vào thao tác làm sạch",
    }
    result = [labels[name] for name, _ in actions if name in labels]
    if any(name.endswith("_scene") for name, _ in scenes):
        result.append("công dụng được suy ra từ bối cảnh sử dụng")
    return _dedupe(result)[:5]


def _fallback_use_cases(industry: str, actions: list[tuple[str, int]]) -> list[str]:
    if industry == "cleaning_goods":
        return ["giúp vệ sinh/lau dọn tiện hơn"]
    if industry == "storage_organization":
        return ["giúp sắp xếp đồ gọn hơn"]
    if industry == "kitchen_goods":
        return ["hỗ trợ thao tác trong bếp"]
    if industry == "beauty_goods":
        return ["hỗ trợ chăm sóc/làm đẹp"]
    if any(name in {"usage_demo", "testing"} for name, _ in actions):
        return ["xem trực tiếp cách dùng trong video"]
    return []


def _fallback_confidence(report: VideoVisualTagReport | None, segments: list[SilentVisualSegment]) -> float:
    tag_confidence = report.average_confidence if report else 0.0
    visual_scores = [segment.visual_score for segment in segments if segment.visual_score is not None]
    visual_confidence = sum(visual_scores) / len(visual_scores) if visual_scores else 0.0
    return round(max(0.25, min(0.62, tag_confidence * 0.55 + visual_confidence * 0.30)), 4)


def _manual_product_label(context: dict | None) -> str:
    if not context:
        return ""
    return _clean_text(context.get("product_name") or context.get("name") or context.get("locked_product_name"))


def _product_lock_enabled(context: dict | None) -> bool:
    if not context:
        return False
    return bool(context.get("product_context_lock_enabled") or context.get("lock_product_context"))


def _normalize_industry(value: object) -> str:
    text = str(value or "").strip()
    allowed = {
        "home_goods",
        "kitchen_goods",
        "desk_setup",
        "storage_organization",
        "beauty_goods",
        "cleaning_goods",
        "dorm_goods",
        "general_product",
    }
    return text if text in allowed else "general_product"


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:120]


def _clean_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.replace(";", "\n").splitlines()
    elif isinstance(value, list):
        items = value
    else:
        items = [value]
    return _dedupe(_clean_text(item) for item in items if _clean_text(item))[:8]


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _float01(value: object, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "y", "co", "có"}:
        return True
    if text in {"0", "false", "no", "n", "khong", "không"}:
        return False
    return default


def _canonical_product_label(value: str) -> str:
    text = _clean_text(value).casefold()
    replacements = {
        "dụng cụ": "",
        "san pham": "",
        "sản phẩm": "",
        "đồ dùng": "",
        "do dung": "",
        "cai": "",
        "cái": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def _most_common_clean(values: list[str]) -> str:
    cleaned = [_clean_text(value) for value in values if _clean_text(value)]
    if not cleaned:
        return ""
    return Counter(cleaned).most_common(1)[0][0]


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()
