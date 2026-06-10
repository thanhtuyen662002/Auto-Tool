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
        lines: list[str] = []
        if name:
            lines.append(f"Nếu bạn đang tìm một món đồ gọn gàng, {name} là lựa chọn đáng xem.")
        else:
            lines.append("Nếu bạn thích đồ dùng gọn gàng, món này khá đáng để xem.")
        lines.extend(captions[: max(0, target_count - 2)])
        lines.append(cta or "Có thể lưu lại để tham khảo khi cần.")
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
