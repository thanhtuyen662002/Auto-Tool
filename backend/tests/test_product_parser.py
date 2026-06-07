from __future__ import annotations

from app.modules.product_import.product_import_schema import RawProductInput
from app.modules.product_import.product_parser import ProductParser


def test_parse_text_extracts_brand_features_and_specs() -> None:
    raw = RawProductInput(
        input_type="text",
        raw_text="""
Máy Chiếu 4K Android KAW XMAX10
Thương hiệu: KAW
Độ sáng 10.000 Lumens
Hỗ trợ 4K
Android 9.0
Thiết kế nhỏ gọn
Phù hợp phòng ngủ, phòng khách, văn phòng
""",
    )

    product = ProductParser().parse(raw)

    assert product.name == "Máy Chiếu 4K Android KAW XMAX10"
    assert product.brand == "KAW"
    assert "Hỗ trợ 4K" in product.features
    assert "Android 9.0" in product.features
    assert any(spec.name == "Độ sáng" and "Lumens" in spec.value for spec in product.specs)


def test_parse_json_aliases_product_name_and_brand_name() -> None:
    raw = RawProductInput(
        input_type="json",
        raw_text="""
{
  "product_name": "Áo chống nắng nữ",
  "brand_name": "SunFit",
  "mo_ta": "Áo chống nắng nhẹ, dễ mặc hằng ngày.",
  "benefits": ["Chất vải nhẹ", "Có mũ che nắng"],
  "specifications": {"Chất liệu": "Polyester"}
}
""",
    )

    product = ProductParser().parse(raw)

    assert product.name == "Áo chống nắng nữ"
    assert product.brand == "SunFit"
    assert product.description == "Áo chống nắng nhẹ, dễ mặc hằng ngày."
    assert product.features == ["Chất vải nhẹ", "Có mũ che nắng"]
    assert product.specs[0].name == "Chất liệu"


def test_parse_csv_uses_first_row_and_adds_warning() -> None:
    raw = RawProductInput(
        input_type="csv",
        raw_text=(
            "name,brand,description,features,cta\n"
            'Máy chiếu KAW,KAW,Nhỏ gọn hỗ trợ 4K,"Hỗ trợ 4K; Android 9.0",Xem ngay\n'
            'Tai nghe ABC,ABC,Âm thanh rõ,"Pin lâu",Xem thêm\n'
        ),
    )

    product = ProductParser().parse(raw)

    assert product.name == "Máy chiếu KAW"
    assert product.brand == "KAW"
    assert product.features == ["Hỗ trợ 4K", "Android 9.0"]
    assert product.warnings == ["CSV có nhiều dòng, hiện tại chỉ import dòng đầu tiên."]
