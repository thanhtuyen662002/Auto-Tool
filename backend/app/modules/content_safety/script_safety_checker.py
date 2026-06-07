from __future__ import annotations

import re
from typing import Any

from app.modules.content_safety.product_claim_checker import RISKY_CLAIM_TERMS
from app.modules.content_safety.safety_schema import SafetyCheckResult, SafetyIssue, build_safety_result
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import ProductInfo


PLACEHOLDERS = ["{product_name}", "{brand}", "{feature}", "CTA:", "Hook:"]

TECHNICAL_CLAIM_PATTERN = re.compile(
    r"\b(?:"
    r"\d+(?:[.,]\d+)?\s?(?:mah|w|inch|cm|kg|g|l|ml|hz|fps|lumens)"
    r"|[48]k"
    r"|ipx\d+"
    r"|upf\s?\d+"
    r"|android\s?\d+(?:[.,]\d+)?"
    r"|bluetooth\s?\d+(?:[.,]\d+)?"
    r")\b",
    re.IGNORECASE,
)


class ScriptSafetyChecker:
    def check_script_against_product(
        self,
        script: ProductVideoScript,
        product: ProductInfo,
        target_duration: float | None = None,
    ) -> SafetyCheckResult:
        issues: list[SafetyIssue] = []
        voiceover_texts = [line.text.strip() for line in script.voiceover if line.text.strip()]
        subtitle_texts = [line.text.strip() for line in script.subtitles if line.text.strip()]
        combined = _script_text(script)

        if not script.hook.strip():
            issues.append(_error("script_empty", "hook", "Hook của script đang rỗng."))
        if not voiceover_texts:
            issues.append(_error("script_empty", "voiceover", "Voiceover của script đang rỗng."))
        if not subtitle_texts:
            issues.append(_error("script_empty", "subtitles", "Subtitle của script đang rỗng."))

        for placeholder in PLACEHOLDERS:
            if placeholder.casefold() in combined.casefold():
                issues.append(
                    SafetyIssue(
                        severity="error",
                        category="placeholder",
                        field="script",
                        message=f"Script còn placeholder hoặc nhãn chưa thay thế: {placeholder}",
                        suggestion="Sửa lại script hoặc dùng fallback script an toàn.",
                    )
                )

        if target_duration:
            estimated_duration = len(" ".join(voiceover_texts)) / 12
            if estimated_duration > target_duration * 1.45:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="script_length",
                        field="voiceover",
                        message="Voiceover có vẻ dài hơn nhiều so với thời lượng video.",
                        suggestion="Rút gọn câu hoặc tăng duration video.",
                    )
                )

        for subtitle in subtitle_texts:
            if len(subtitle) > 95:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="subtitle_length",
                        field="subtitles",
                        message="Có subtitle quá dài, dễ khó đọc trên video.",
                        suggestion="Tách thành câu ngắn hơn nhưng không tách nửa câu.",
                    )
                )
                break

        if len(script.caption.strip()) > 260:
            issues.append(
                SafetyIssue(
                    severity="warning",
                    category="caption_length",
                    field="caption",
                    message="Caption khá dài.",
                    suggestion="Rút gọn caption để dễ đăng lên TikTok/Shopee/Reels.",
                )
            )

        for term in RISKY_CLAIM_TERMS:
            if term in combined.casefold():
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="risky_claim",
                        field="script",
                        message=f"Script có claim mạnh: '{term}'.",
                        suggestion="Dùng cách nói trung tính hơn nếu thông tin chưa được chứng minh.",
                    )
                )

        product_text = _normalized_product_text(product)
        for claim in _technical_claims(combined):
            if _normalize_claim(claim) not in product_text:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="unsupported_spec_claim",
                        field="script",
                        message=f"Script có thông số kỹ thuật chưa thấy trong product info: {claim}",
                        suggestion="Chỉ dùng specs/features người dùng đã cung cấp.",
                    )
                )
        return build_safety_result(issues)


def _error(category: str, field: str, message: str) -> SafetyIssue:
    return SafetyIssue(
        severity="error",
        category=category,
        field=field,
        message=message,
        suggestion="Sửa nội dung trước khi render.",
    )


def _script_text(script: ProductVideoScript) -> str:
    parts = [
        script.hook,
        script.cta,
        script.caption,
        *script.hashtags,
        *(line.text for line in script.voiceover),
        *(line.text for line in script.subtitles),
    ]
    return " ".join(parts)


def _technical_claims(text: str) -> list[str]:
    seen: set[str] = set()
    claims: list[str] = []
    for match in TECHNICAL_CLAIM_PATTERN.finditer(text):
        claim = " ".join(match.group(0).split())
        key = _normalize_claim(claim)
        if key in seen:
            continue
        seen.add(key)
        claims.append(claim)
    return claims


def _normalized_product_text(product: ProductInfo) -> str:
    parts: list[str] = [
        product.name,
        product.brand,
        product.description,
        product.cta,
        *product.features,
        *product.validation_warnings,
        *product.hashtag_suggestions,
    ]
    parts.extend(f"{spec.name} {spec.value}" for spec in product.specs)
    return _normalize_claim(" ".join(parts))


def _normalize_claim(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())
