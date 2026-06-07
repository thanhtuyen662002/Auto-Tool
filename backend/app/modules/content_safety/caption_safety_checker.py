from __future__ import annotations

from typing import Any

from app.modules.content_safety.product_claim_checker import RISKY_CLAIM_TERMS
from app.modules.content_safety.safety_schema import SafetyCheckResult, SafetyIssue, build_safety_result
from app.schemas.project_schema import ProductInfo


WRONG_INDUSTRY_HASHTAG_HINTS = {
    "#trimun": ["mụn", "serum", "kem", "skincare", "da"],
    "#giamcan": ["giảm cân", "ăn kiêng", "thực phẩm"],
    "#mevabe": ["bé", "mẹ", "trẻ em", "bỉm", "sữa"],
    "#congnghe": ["máy", "điện", "camera", "android", "bluetooth", "4k"],
}


class CaptionSafetyChecker:
    def check_caption(self, caption: str, hashtags: list[str], product: ProductInfo) -> SafetyCheckResult:
        issues: list[SafetyIssue] = []
        cleaned_caption = " ".join(str(caption or "").split())
        normalized_hashtags = normalize_hashtags_for_safety(hashtags)

        if not cleaned_caption:
            issues.append(
                SafetyIssue(
                    severity="error",
                    category="caption_empty",
                    field="caption",
                    message="Caption đang rỗng.",
                    suggestion="Bổ sung caption trước khi export nội dung.",
                )
            )
        if len(cleaned_caption) > 280:
            issues.append(
                SafetyIssue(
                    severity="warning",
                    category="caption_length",
                    field="caption",
                    message="Caption quá dài.",
                    suggestion="Rút gọn caption để dễ đăng và dễ đọc.",
                )
            )

        lower_caption = cleaned_caption.casefold()
        for term in RISKY_CLAIM_TERMS:
            if term in lower_caption:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="risky_claim",
                        field="caption",
                        message=f"Caption có claim mạnh: '{term}'.",
                        suggestion="Kiểm tra lại claim trước khi đăng.",
                    )
                )

        if len(normalized_hashtags) > 8:
            issues.append(
                SafetyIssue(
                    severity="warning",
                    category="hashtag_spam",
                    field="hashtags",
                    message="Hashtag nhiều hơn 8 cái.",
                    suggestion="Giữ 3-8 hashtag liên quan nhất.",
                )
            )

        for original, normalized in zip(hashtags, normalized_hashtags):
            if str(original).strip() != normalized:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="hashtag_format",
                        field="hashtags",
                        message=f"Hashtag '{original}' sẽ được normalize thành '{normalized}'.",
                        suggestion="Hashtag nên bắt đầu bằng # và không có khoảng trắng.",
                    )
                )
            if " " in normalized:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="hashtag_format",
                        field="hashtags",
                        message=f"Hashtag có khoảng trắng: '{normalized}'.",
                        suggestion="Dùng hashtag liền chữ, ví dụ #reviewcongnghe.",
                    )
                )

        product_text = _product_text(product)
        for hashtag in normalized_hashtags:
            hints = WRONG_INDUSTRY_HASHTAG_HINTS.get(hashtag.casefold())
            if hints and not any(hint in product_text for hint in hints):
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="wrong_industry_hashtag",
                        field="hashtags",
                        message=f"Hashtag '{hashtag}' có vẻ không khớp ngành hàng sản phẩm.",
                        suggestion="Kiểm tra lại hashtag trước khi export nội dung.",
                    )
                )
        return build_safety_result(issues)


def normalize_hashtags_for_safety(hashtags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in hashtags or []:
        item = " ".join(str(raw).strip().split())
        if not item:
            continue
        item = item.replace(" ", "")
        if not item.startswith("#"):
            item = f"#{item}"
        key = item.casefold()
        if key in seen:
            continue
        normalized.append(item)
        seen.add(key)
    return normalized


def _product_text(product: Any) -> str:
    parts = [
        product.name,
        product.brand,
        product.description,
        product.cta,
        *product.features,
        *(f"{spec.name} {spec.value}" for spec in product.specs),
    ]
    return " ".join(parts).casefold()
