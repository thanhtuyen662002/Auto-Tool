from __future__ import annotations

from app.modules.product_import.product_import_schema import ProductInfoNormalized
from app.modules.product_import.product_normalizer import ProductNormalizer
from app.schemas.project_schema import ProductSpec


def test_normalize_removes_duplicate_features_and_limits_description() -> None:
    product = ProductInfoNormalized(
        name="  Máy chiếu KAW  ",
        brand=" KAW ",
        description=" ".join(["Mô tả dài"] * 80),
        features=["- Hỗ trợ 4K", "Hỗ trợ 4K", "* Android 9.0", "", "Thiết kế nhỏ gọn"],
        specs=[ProductSpec(name=" Độ sáng ", value=" 10.000 Lumens "), ProductSpec(name="Độ sáng", value="10.000 Lumens")],
        hashtag_suggestions=["#Review", "Review", "Sản phẩm"],
    )

    normalized = ProductNormalizer().normalize(product)

    assert normalized.name == "Máy chiếu KAW"
    assert normalized.brand == "KAW"
    assert normalized.features == ["Hỗ trợ 4K", "Android 9.0", "Thiết kế nhỏ gọn"]
    assert len(normalized.description) <= 220
    assert len(normalized.specs) == 1
    assert normalized.hashtag_suggestions == ["#review", "#sanpham"]


def test_normalize_uses_industry_default_cta() -> None:
    product = ProductInfoNormalized(
        name="Son dưỡng",
        description="Son dưỡng môi dùng hằng ngày.",
        features=["Dễ dùng", "Nhỏ gọn"],
        industry_preset_id="beauty_cosmetics",
        cta="",
    )

    normalized = ProductNormalizer().normalize(product)

    assert normalized.cta == "Xem chi tiết trước khi chọn mua"
