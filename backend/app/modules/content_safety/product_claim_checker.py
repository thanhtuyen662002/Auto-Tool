from __future__ import annotations

from typing import Any

from app.modules.content_safety.safety_schema import SafetyCheckResult, SafetyIssue, build_safety_result


RISKY_CLAIM_TERMS = [
    "tốt nhất",
    "số 1",
    "100% hiệu quả",
    "cam kết khỏi",
    "trị bệnh",
    "chữa bệnh",
    "hết mụn",
    "hết nám",
    "trắng bật tông",
    "giảm cân thần tốc",
    "an toàn tuyệt đối",
    "không tác dụng phụ",
]

SENSITIVE_INDUSTRIES = {"beauty_cosmetics", "food_beverage", "mom_baby"}

SENSITIVE_CLAIM_TERMS = [
    "trị mụn",
    "trị nám",
    "chữa",
    "khỏi bệnh",
    "giảm cân",
    "dứt điểm",
    "an toàn tuyệt đối",
]


class ProductClaimChecker:
    def check_product_info(self, product: Any, industry_preset_id: str | None = None) -> SafetyCheckResult:
        issues: list[SafetyIssue] = []
        name = _value(product, "name")
        description = _value(product, "description")
        features = _list_value(product, "features")
        brand = _value(product, "brand")

        if not name:
            issues.append(
                SafetyIssue(
                    severity="error",
                    category="missing_required_product_info",
                    field="name",
                    message="Thiếu tên sản phẩm.",
                    suggestion="Bổ sung tên sản phẩm trước khi render.",
                )
            )
        if not description and not features:
            issues.append(
                SafetyIssue(
                    severity="error",
                    category="missing_required_product_info",
                    field="description",
                    message="Thiếu mô tả hoặc điểm nổi bật của sản phẩm.",
                    suggestion="Bổ sung mô tả ngắn hoặc ít nhất một điểm nổi bật.",
                )
            )
        if not brand:
            issues.append(
                SafetyIssue(
                    severity="warning",
                    category="missing_optional_product_info",
                    field="brand",
                    message="Thiếu thương hiệu.",
                    suggestion="Nếu có thương hiệu, hãy bổ sung để script rõ ngữ cảnh hơn.",
                )
            )

        text = _combined_product_text(product)
        for term in RISKY_CLAIM_TERMS:
            if term in text:
                issues.append(
                    SafetyIssue(
                        severity="warning",
                        category="risky_claim",
                        field="product",
                        message=f"Có claim mạnh: '{term}'. Nên kiểm tra lại trước khi render.",
                        suggestion="Đổi sang cách nói trung tính hơn nếu chưa có bằng chứng rõ ràng.",
                    )
                )

        if industry_preset_id in SENSITIVE_INDUSTRIES and (
            any(term in text for term in RISKY_CLAIM_TERMS)
            or any(term in text for term in SENSITIVE_CLAIM_TERMS)
        ):
            issues.append(
                SafetyIssue(
                    severity="warning",
                    category="sensitive_industry_claim",
                    field="product",
                    message="Ngành hàng nhạy cảm có claim mạnh, cần kiểm tra kỹ trước khi dùng trong quảng cáo.",
                    suggestion="Không nói quá công dụng và chỉ dùng thông tin người dùng đã cung cấp.",
                )
            )
        return build_safety_result(issues)


def _combined_product_text(product: Any) -> str:
    parts = [
        _value(product, "name"),
        _value(product, "brand"),
        _value(product, "description"),
        _value(product, "cta"),
        *_list_value(product, "features"),
        *_list_value(product, "validation_warnings"),
        *_spec_texts(product),
    ]
    return " ".join(parts).casefold()


def _spec_texts(product: Any) -> list[str]:
    specs = getattr(product, "specs", None)
    if specs is None and isinstance(product, dict):
        specs = product.get("specs")
    result: list[str] = []
    for spec in specs or []:
        name = _value(spec, "name")
        value = _value(spec, "value")
        if name or value:
            result.append(f"{name} {value}")
    return result


def _value(obj: Any, field: str) -> str:
    value = obj.get(field) if isinstance(obj, dict) else getattr(obj, field, "")
    return " ".join(str(value or "").strip().split())


def _list_value(obj: Any, field: str) -> list[str]:
    value = obj.get(field) if isinstance(obj, dict) else getattr(obj, field, [])
    return [" ".join(str(item).strip().split()) for item in (value or []) if str(item).strip()]
