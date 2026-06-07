from __future__ import annotations

from app.modules.product_import.product_import_schema import ProductInfoNormalized, RawProductInput
from app.modules.product_import.product_import_service import ProductImportService
from app.modules.product_import.product_validator import ProductValidator


def test_missing_name_returns_error() -> None:
    product = ProductInfoNormalized(description="Có mô tả", features=["Dễ dùng"], cta="Xem ngay")

    issues = ProductValidator().validate(product)

    assert any(issue.field == "name" and issue.severity == "error" for issue in issues)


def test_claim_risk_returns_warning() -> None:
    product = ProductInfoNormalized(
        name="Serum test",
        brand="ABC",
        description="Serum giúp hết mụn và trắng bật tông.",
        features=["Dưỡng da", "Dễ dùng"],
        industry_preset_id="beauty_cosmetics",
        cta="Xem ngay",
    )

    issues = ProductValidator().validate(product)

    assert any(issue.field == "claims" and issue.severity == "warning" for issue in issues)


def test_confidence_score_is_reasonable() -> None:
    result = ProductImportService().import_product_info(
        RawProductInput(
            input_type="text",
            raw_text="""
Máy chiếu KAW
Thương hiệu: KAW
Hỗ trợ 4K
Android 9.0
Thiết kế nhỏ gọn
""",
        )
    )

    assert result.success is True
    assert result.product is not None
    assert 0.6 <= result.product.confidence_score <= 1.0
