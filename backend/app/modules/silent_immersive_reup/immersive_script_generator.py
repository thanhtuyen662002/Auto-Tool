from __future__ import annotations

import re

from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan


class ImmersiveScriptGenerator:
    def generate_voiceover_script(
        self,
        plan: SilentReupPlan,
        product_context: dict | None,
        style: str,
    ) -> str:
        duration = _plan_duration(plan)
        target_count = 3 if duration <= 10 else 5 if duration <= 18 else 7
        captions = [caption.text for caption in plan.captions if caption.text.strip()]
        name = str((product_context or {}).get("product_name") or (product_context or {}).get("name") or "").strip()
        cta = str((product_context or {}).get("cta") or "").strip()
        features = _features(product_context)

        lines: list[str] = []
        if name:
            lines.append(f"Nếu bạn đang cân nhắc {name}, hãy xem nhanh cách sản phẩm xuất hiện trong video này.")
            if features:
                lines.append(f"Điểm đáng chú ý là {features[0]}.")
        else:
            lines.append("Mình giữ lại các cảnh rõ nhất để bạn xem cách sản phẩm được dùng trong thực tế.")
            lines.append("Hãy chú ý phần thao tác, kích thước và chi tiết xuất hiện trực tiếp trên video.")

        remaining = max(0, target_count - len(lines) - 1)
        lines.extend(_safe_caption_lines(captions, remaining, has_product_context=bool(name or features)))
        lines.append(cta or "Bạn có thể lưu lại để so sánh thêm trước khi chọn mua.")
        return " ".join(_clean_sentence(line) for line in lines[:target_count] if _clean_sentence(line))


def _plan_duration(plan: SilentReupPlan) -> float:
    if plan.captions:
        return max(caption.end for caption in plan.captions)
    if plan.visual_segments:
        return max(segment.end for segment in plan.visual_segments)
    return 8.0


def _clean_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _features(product_context: dict | None) -> list[str]:
    raw = (product_context or {}).get("features") or (product_context or {}).get("locked_product_keywords") or []
    if isinstance(raw, str):
        raw = [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _safe_caption_lines(captions: list[str], limit: int, *, has_product_context: bool) -> list[str]:
    if limit <= 0:
        return []
    if has_product_context:
        return captions[:limit]
    generic = [
        "Phần quay cận cảnh giúp nhìn rõ hơn chất liệu và kiểu dáng.",
        "Các thao tác trong video cho thấy cách dùng cơ bản của sản phẩm.",
        "Bạn nên xem kỹ từng cảnh để tự đánh giá có phù hợp nhu cầu không.",
    ]
    return generic[:limit]
