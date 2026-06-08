from __future__ import annotations

from app.modules.product_import.product_import_schema import RawProductInput
from app.modules.product_import.product_parser import ProductParser


def test_parse_shopee_extension_prefers_structured_data() -> None:
    raw = RawProductInput(
        input_type="shopee_extension",
        source_name="shopee",
        source_url="https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        raw_text="Ten san pham: fallback",
        structured_data={
            "name": "May chieu KAW XMAX10",
            "brand": "KAW",
            "description": "May chieu mini ho tro 4K va Android 9.0.",
            "features": ["Ho tro 4K", "Android 9.0", "Ho tro 4K"],
            "specs": [{"name": "Do sang", "value": "10000 Lumens"}],
            "cta": "Xem chi tiet san pham tren Shopee",
            "price": "1.990.000d",
            "shop": {"name": "KAW Official"},
            "shopee": {"warnings": []},
        },
    )

    product = ProductParser().parse(raw)

    assert product.name == "May chieu KAW XMAX10"
    assert product.brand == "KAW"
    assert product.features == ["Ho tro 4K", "Android 9.0"]
    assert any(spec.name == "Do sang" and spec.value == "10000 Lumens" for spec in product.specs)
    assert any(spec.name == "Gia" and spec.value == "1.990.000d" for spec in product.specs)
    assert product.cta == "Xem chi tiet san pham tren Shopee"


def test_parse_shopee_extension_falls_back_to_raw_text() -> None:
    raw = RawProductInput(
        input_type="shopee_extension",
        source_name="shopee",
        source_url="https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
        raw_text="""
May chieu KAW XMAX10
Brand: KAW
Feature: Ho tro 4K; Android 9.0
Do sang: 10000 Lumens
""",
    )

    product = ProductParser().parse(raw)

    assert product.name == "May chieu KAW XMAX10"
    assert product.brand == "KAW"
    assert product.features == ["Ho tro 4K", "Android 9.0"]
    assert any(spec.name == "Do sang" for spec in product.specs)
