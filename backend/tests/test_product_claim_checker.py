from __future__ import annotations

from app.modules.content_safety.product_claim_checker import ProductClaimChecker
from app.modules.product_import.product_import_schema import ProductInfoNormalized


def test_product_missing_name_returns_error() -> None:
    product = ProductInfoNormalized(name="", description="Mô tả có sẵn", features=["Dễ dùng"])

    result = ProductClaimChecker().check_product_info(product)

    assert result.passed is False
    assert any(issue.severity == "error" and issue.field == "name" for issue in result.issues)


def test_product_risky_claim_returns_warning() -> None:
    product = ProductInfoNormalized(
        name="Sản phẩm A",
        brand="ABC",
        description="Sản phẩm này 100% hiệu quả khi sử dụng.",
        features=["Dễ dùng"],
    )

    result = ProductClaimChecker().check_product_info(product)

    assert result.passed is True
    assert any(issue.category == "risky_claim" and issue.severity == "warning" for issue in result.issues)


def test_beauty_sensitive_claim_returns_warning() -> None:
    product = ProductInfoNormalized(
        name="Serum ABC",
        brand="ABC",
        description="Serum hỗ trợ chăm sóc da.",
        features=["Trị mụn dứt điểm", "Dễ dùng"],
    )

    result = ProductClaimChecker().check_product_info(product, industry_preset_id="beauty_cosmetics")

    assert result.passed is True
    assert any(issue.category == "sensitive_industry_claim" for issue in result.issues)
