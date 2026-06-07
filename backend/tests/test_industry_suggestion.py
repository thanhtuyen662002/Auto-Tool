from __future__ import annotations

from app.modules.product_import.product_import_schema import ProductInfoNormalized
from app.modules.product_import.product_import_service import suggest_industry_preset


def test_suggest_projector_as_tech_electronics() -> None:
    product = ProductInfoNormalized(name="Máy chiếu 4K Android", features=["Hỗ trợ 4K"])

    assert suggest_industry_preset(product) == "tech_electronics"


def test_suggest_sun_jacket_as_fashion() -> None:
    product = ProductInfoNormalized(name="Áo chống nắng nữ", features=["Chất vải nhẹ"])

    assert suggest_industry_preset(product) == "fashion_accessories"


def test_suggest_baby_tissue_as_mom_baby() -> None:
    product = ProductInfoNormalized(name="Khăn giấy cho bé", features=["Mềm mại", "Dễ dùng"])

    assert suggest_industry_preset(product) == "mom_baby"
