from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.modules.industry_presets.industry_schema import IndustryPreset


DEFAULT_INDUSTRY_PRESET_ID = "general_product"


_PRESET_DATA: list[dict[str, Any]] = [
    {
        "id": "general_product",
        "name": "Sản phẩm tổng quát",
        "description": "Preset an toàn cho hầu hết sản phẩm phổ thông.",
        "recommended_for": ["sản phẩm phổ thông", "đồ tiện ích", "mua sắm online"],
        "default_video_style": "Review tự nhiên",
        "default_edit_strength": "Vừa",
        "timeline_template_id": "ugc_reviewer_natural",
        "visual_style_preset_id": "clean_review_light",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["reviewer_natural", "benefit_first", "use_case_scene"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Tự nhiên, rõ ràng, tập trung vào lợi ích thực tế và tình huống sử dụng.",
        "hashtag_suggestions": ["#review", "#sanpham", "#muasam", "#tienich"],
    },
    {
        "id": "tech_electronics",
        "name": "Công nghệ / Điện tử",
        "description": "Phù hợp sản phẩm công nghệ, phụ kiện điện tử, thiết bị thông minh.",
        "recommended_for": [
            "máy chiếu",
            "tai nghe",
            "bàn phím",
            "chuột",
            "loa",
            "camera",
            "đèn LED",
            "phụ kiện điện thoại",
        ],
        "default_video_style": "Showcase sản phẩm sạch đẹp",
        "default_edit_strength": "Vừa",
        "timeline_template_id": "product_showcase_clean",
        "visual_style_preset_id": "tech_dark_neon",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["benefit_first", "reviewer_natural", "use_case_scene"],
        "default_tts_voice": "vi-VN-NamMinhNeural",
        "caption_tone": "Rõ ràng, nhấn vào tính năng, trải nghiệm sử dụng và lợi ích thực tế.",
        "hashtag_suggestions": ["#congnghe", "#reviewcongnghe", "#phukien", "#dientu", "#sanphamhot"],
    },
    {
        "id": "beauty_cosmetics",
        "name": "Mỹ phẩm / Làm đẹp",
        "description": "Phù hợp sản phẩm làm đẹp, skincare, makeup, chăm sóc cá nhân.",
        "recommended_for": ["mỹ phẩm", "skincare", "makeup", "máy làm đẹp", "phụ kiện làm đẹp"],
        "default_video_style": "Review tự nhiên",
        "default_edit_strength": "Nhẹ",
        "timeline_template_id": "ugc_reviewer_natural",
        "visual_style_preset_id": "beauty_soft_glow",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["reviewer_natural", "benefit_first", "use_case_scene"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Mềm mại, gần gũi, nhấn vào cảm giác sử dụng và sự tiện lợi.",
        "hashtag_suggestions": ["#lamdep", "#skincare", "#beautyreview", "#mypham", "#chamsocbanthan"],
        "notes": [
            "Không claim quá đà về hiệu quả làm trắng, trị mụn, trị nám, chữa bệnh da liễu nếu không có thông tin được cung cấp."
        ],
    },
    {
        "id": "fashion_accessories",
        "name": "Thời trang / Phụ kiện",
        "description": "Phù hợp quần áo, áo chống nắng, phụ kiện thời trang.",
        "recommended_for": ["áo chống nắng", "áo khoác", "túi", "giày dép", "mũ", "phụ kiện thời trang"],
        "default_video_style": "Showcase sản phẩm sạch đẹp",
        "default_edit_strength": "Nhẹ",
        "timeline_template_id": "product_showcase_clean",
        "visual_style_preset_id": "fashion_minimal",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["benefit_first", "use_case_scene", "reviewer_natural"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Tối giản, nhấn vào form dáng, chất liệu, màu sắc, cách phối và tình huống sử dụng.",
        "hashtag_suggestions": ["#thoitrang", "#phukien", "#aokhoac", "#ootd", "#reviewthoitrang"],
    },
    {
        "id": "home_lifestyle",
        "name": "Gia dụng / Tiện ích nhà cửa",
        "description": "Phù hợp sản phẩm gia dụng, đồ bếp, tiện ích nhà cửa.",
        "recommended_for": ["đồ gia dụng", "đồ bếp", "đồ dọn dẹp", "thiết bị tiện ích nhà cửa"],
        "default_video_style": "Vấn đề -> Giải pháp",
        "default_edit_strength": "Vừa",
        "timeline_template_id": "problem_solution",
        "visual_style_preset_id": "clean_review_light",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["problem_hook", "use_case_scene", "benefit_first"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Đời thường, tập trung vào vấn đề thường gặp và cách sản phẩm giúp việc nhà tiện hơn.",
        "hashtag_suggestions": ["#giadung", "#tienichnhacua", "#meovatgiadinh", "#reviewgiadung", "#nhacua"],
    },
    {
        "id": "mom_baby",
        "name": "Mẹ và bé",
        "description": "Phù hợp đồ dùng mẹ và bé, sản phẩm gia đình phong cách dễ thương.",
        "recommended_for": ["đồ cho mẹ", "đồ cho bé", "đồ dùng gia đình nhẹ nhàng"],
        "default_video_style": "Review tự nhiên",
        "default_edit_strength": "Nhẹ",
        "timeline_template_id": "ugc_reviewer_natural",
        "visual_style_preset_id": "cute_pastel_shop",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["reviewer_natural", "use_case_scene", "problem_hook"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Ấm áp, nhẹ nhàng, tập trung vào sự tiện lợi và cảm giác yên tâm khi dùng.",
        "hashtag_suggestions": ["#mevabe", "#dodungchobe", "#reviewmevabe", "#giadinh", "#tienich"],
        "notes": ["Không đưa claim y tế, sức khỏe, an toàn tuyệt đối nếu không có thông tin rõ ràng."],
    },
    {
        "id": "food_beverage",
        "name": "Đồ ăn / Đồ uống",
        "description": "Phù hợp sản phẩm ăn uống, coffee, trà, bánh, thực phẩm đóng gói.",
        "recommended_for": ["đồ ăn", "đồ uống", "cà phê", "trà", "bánh", "gia vị", "thực phẩm đóng gói"],
        "default_video_style": "Review tự nhiên",
        "default_edit_strength": "Vừa",
        "timeline_template_id": "ugc_reviewer_natural",
        "visual_style_preset_id": "food_warm_label",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["use_case_scene", "reviewer_natural", "benefit_first"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Gợi cảm giác ngon miệng, gần gũi, nhấn vào dịp sử dụng và trải nghiệm.",
        "hashtag_suggestions": ["#doan", "#douong", "#foodreview", "#coffee", "#anuong"],
        "notes": ["Không claim công dụng sức khỏe, giảm cân, chữa bệnh nếu không có dữ liệu được cung cấp."],
    },
    {
        "id": "fast_sale_trending",
        "name": "Sale nhanh / Sản phẩm trend",
        "description": "Phù hợp video nhịp nhanh, hook mạnh, CTA rõ.",
        "recommended_for": [
            "sản phẩm trend",
            "hàng sale",
            "sản phẩm cần CTA mạnh",
            "video ngắn nhịp nhanh",
        ],
        "default_video_style": "Cắt nhanh kiểu TikTok",
        "default_edit_strength": "Mạnh",
        "timeline_template_id": "fast_tiktok_recut",
        "visual_style_preset_id": "sale_bold_red",
        "script_variation_mode": "auto_mix",
        "preferred_script_variant_ids": ["fast_sales", "benefit_first", "problem_hook"],
        "default_tts_voice": "vi-VN-HoaiMyNeural",
        "caption_tone": "Ngắn, rõ, nhiều năng lượng, nhấn ưu đãi hoặc lý do nên xem ngay.",
        "hashtag_suggestions": ["#sale", "#sanphamhot", "#dealhot", "#muasam", "#tiktokmademebuyit"],
        "notes": [
            "Không dùng từ spam quá mức, không tạo khuyến mãi giả nếu người dùng không cung cấp."
        ],
    },
]


def list_industry_presets() -> list[IndustryPreset]:
    return [_preset_from_data(data) for data in _PRESET_DATA]


def get_industry_preset(preset_id: str | None) -> IndustryPreset:
    lookup = (preset_id or DEFAULT_INDUSTRY_PRESET_ID).strip()
    for data in _PRESET_DATA:
        if data["id"] == lookup:
            return _preset_from_data(data)
    return _preset_from_data(next(data for data in _PRESET_DATA if data["id"] == DEFAULT_INDUSTRY_PRESET_ID))


def industry_preset_exists(preset_id: str) -> bool:
    return any(data["id"] == preset_id for data in _PRESET_DATA)


def _preset_from_data(data: dict[str, Any]) -> IndustryPreset:
    return IndustryPreset.model_validate(deepcopy(data))

