from __future__ import annotations

from app.modules.product_import.product_import_schema import ProductInfoNormalized, ProductValidationIssue


CLAIM_RISK_TERMS = [
    "100% hiệu quả",
    "tốt nhất",
    "số 1",
    "trị bệnh",
    "chữa bệnh",
    "giảm cân thần tốc",
    "trắng bật tông",
    "hết mụn",
    "hết nám",
    "an toàn tuyệt đối",
    "cam kết khỏi",
]

SENSITIVE_INDUSTRIES = {"beauty_cosmetics", "food_beverage", "mom_baby"}

SENSITIVE_CLAIMS = [
    "trị",
    "chữa",
    "khỏi bệnh",
    "giảm cân",
    "hết mụn",
    "hết nám",
    "trắng bật tông",
    "an toàn tuyệt đối",
]

VAGUE_CLAIMS = [
    "siêu bền",
    "cực tốt",
    "đỉnh nhất",
    "xịn nhất",
]


class ProductValidator:
    def validate(self, product: ProductInfoNormalized) -> list[ProductValidationIssue]:
        issues: list[ProductValidationIssue] = []
        if not product.name.strip():
            issues.append(
                ProductValidationIssue(
                    field="name",
                    severity="error",
                    message="Thiếu tên sản phẩm.",
                    suggestion="Hãy bổ sung tên sản phẩm rõ ràng trước khi tạo script.",
                )
            )
        if not product.description.strip() and not product.features:
            issues.append(
                ProductValidationIssue(
                    field="description",
                    severity="error",
                    message="Thiếu mô tả hoặc điểm nổi bật của sản phẩm.",
                    suggestion="Hãy thêm mô tả ngắn hoặc ít nhất một vài điểm nổi bật.",
                )
            )
        if not (product.brand or "").strip():
            issues.append(
                ProductValidationIssue(
                    field="brand",
                    severity="warning",
                    message="Thiếu thương hiệu.",
                    suggestion="Nếu sản phẩm có thương hiệu, hãy bổ sung để script tự nhiên hơn.",
                )
            )
        if not product.cta.strip():
            issues.append(
                ProductValidationIssue(
                    field="cta",
                    severity="warning",
                    message="Thiếu CTA.",
                    suggestion="Có thể dùng CTA mặc định: Xem chi tiết sản phẩm ngay.",
                )
            )
        if not product.industry_preset_id:
            issues.append(
                ProductValidationIssue(
                    field="industry_preset_id",
                    severity="warning",
                    message="Chưa có ngành hàng gợi ý.",
                    suggestion="Chọn ngành hàng để prompt script an toàn hơn.",
                )
            )

        text = _combined_product_text(product)
        for term in CLAIM_RISK_TERMS:
            if term in text:
                issues.append(
                    ProductValidationIssue(
                        field="claims",
                        severity="warning",
                        message=f'Nội dung có claim mạnh "{term}", nên kiểm tra lại trước khi dùng trong quảng cáo.',
                        suggestion="Hãy đổi sang cách nói trung tính nếu chưa có bằng chứng rõ ràng.",
                    )
                )

        if product.industry_preset_id in SENSITIVE_INDUSTRIES:
            for term in SENSITIVE_CLAIMS:
                if term in text:
                    issues.append(
                        ProductValidationIssue(
                            field="claims",
                            severity="warning",
                            message="Ngành hàng nhạy cảm có claim sức khỏe/làm đẹp khá mạnh.",
                            suggestion="Không nói quá công dụng và chỉ dùng thông tin người dùng đã cung cấp.",
                        )
                    )
                    break

        for term in VAGUE_CLAIMS:
            if term in text:
                issues.append(
                    ProductValidationIssue(
                        field="features",
                        severity="warning",
                        message=f'Nội dung có claim cảm tính "{term}".',
                        suggestion="Nên thay bằng mô tả cụ thể hơn nếu có dữ liệu.",
                    )
                )

        if product.description and len(product.description) < 25:
            issues.append(
                ProductValidationIssue(
                    field="description",
                    severity="info",
                    message="Mô tả sản phẩm còn ngắn.",
                    suggestion="Có thể bổ sung tình huống sử dụng hoặc lợi ích chính.",
                )
            )
        if len(product.features) < 2:
            issues.append(
                ProductValidationIssue(
                    field="features",
                    severity="info",
                    message="Điểm nổi bật còn ít.",
                    suggestion="Nên có 3 điểm nổi bật trở lên để tạo nhiều biến thể script.",
                )
            )
        return issues


def _combined_product_text(product: ProductInfoNormalized) -> str:
    parts = [
        product.name,
        product.brand or "",
        product.description,
        product.cta,
        *product.features,
        *(f"{spec.name} {spec.value}" for spec in product.specs),
    ]
    return " ".join(parts).casefold()
