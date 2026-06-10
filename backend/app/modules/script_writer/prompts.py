from __future__ import annotations


def build_product_video_script_prompt(
    product,
    render_settings,
    ai_settings,
    output_index: int = 1,
    industry=None,
) -> str:
    features = "\n".join(f"- {feature}" for feature in product.features)
    specs = _format_specs(getattr(product, "specs", []))
    product_warnings = _format_product_warnings(getattr(product, "validation_warnings", []))
    duration = float(render_settings.duration)
    line_count = recommended_line_count(duration)
    angle = variant_angle(output_index)
    industry_context = _industry_prompt_context(industry)
    return f"""
Bạn là chuyên gia viết nội dung video quảng cáo ngắn cho TikTok/Shopee/Reels.

Hãy viết kịch bản video tiếng Việt cho sản phẩm sau:

Tên sản phẩm:
{product.name}

Thương hiệu:
{product.brand}

Mô tả:
{product.description}

Điểm nổi bật:
{features}

Thông số được cung cấp:
{specs}

{product_warnings}

CTA:
{product.cta}

{industry_context}

Yêu cầu:
- Đây là biến thể video số {output_index}
- Góc tiếp cận riêng cho biến thể này: {angle}
- Nội dung biến thể này phải khác cách mở đầu và cách diễn đạt của các output khác
- Video dài khoảng {duration:g} giây
- Voiceover phải phủ gần đủ thời lượng video, không chỉ 10-12 giây đầu
- Voiceover chia thành khoảng {line_count} đoạn, mỗi đoạn là một câu hoàn chỉnh
- Mốc time_hint phải bắt đầu từ 0 và đoạn cuối phải kết thúc gần {duration:g}s
- Subtitles phải đồng bộ với voiceover, start_hint/end_hint phủ gần đủ {duration:g}s
- Giọng văn tự nhiên như reviewer Việt Nam
- Ngôn ngữ: {ai_settings.language}
- Tone: {ai_settings.tone}
- Chỉ được dùng specs có trong danh sách "Thông số được cung cấp"
- Không nói quá sự thật
- Không dùng claim tuyệt đối như "tốt nhất", "số 1", "100% hiệu quả" nếu thông tin không được cung cấp
- Không bịa thêm thông số kỹ thuật
- Câu ngắn, dễ đọc subtitle
- Không tách nửa câu thành nhiều subtitle nhỏ
- CTA rõ nhưng không spam
- Trả về JSON hợp lệ, không markdown, không giải thích
- Chỉ trả JSON object duy nhất, không thêm text trước hoặc sau JSON

Schema JSON bắt buộc:

{{
  "hook": "string",
  "voiceover": [
    {{
      "time_hint": "0-3s",
      "text": "string"
    }}
  ],
  "subtitles": [
    {{
      "start_hint": 0,
      "end_hint": 3,
      "text": "string"
    }}
  ],
  "cta": "string",
  "caption": "string",
  "hashtags": ["string"]
}}
""".strip()


def _format_specs(specs) -> str:
    items = []
    for spec in specs or []:
        name = getattr(spec, "name", "")
        value = getattr(spec, "value", "")
        if name and value:
            items.append(f"- {name}: {value}")
    return "\n".join(items) if items else "- Không có thông số cụ thể được cung cấp."


def _format_product_warnings(warnings: list[str]) -> str:
    cleaned = [" ".join(str(item).split()) for item in warnings if str(item).strip()]
    if not cleaned:
        return ""
    lines = "\n".join(f"- {item}" for item in cleaned[:6])
    return f"""Cảnh báo nội dung:
{lines}
"""


def _industry_prompt_context(industry) -> str:
    if industry is None:
        return ""
    hashtags = ", ".join(industry.hashtag_suggestions)
    preferred = ", ".join(industry.preferred_script_variant_ids)
    notes = "\n".join(f"- {note}" for note in industry.notes)
    if not notes:
        notes = "- Không tạo claim sai sự thật theo ngành hàng."
    return f"""
Ngành hàng:
{industry.name}

Caption tone:
{industry.caption_tone}

Hashtag gợi ý:
{hashtags}

Preferred script styles:
{preferred}

Lưu ý an toàn theo ngành:
{notes}

Yêu cầu thêm theo ngành:
- Caption phải phù hợp ngành hàng.
- Hashtag có thể dùng hashtag gợi ý nhưng không spam.
- Không tạo claim sai sự thật theo ngành hàng.
""".strip()


def recommended_line_count(duration: float) -> int:
    if duration <= 15:
        return 3
    if duration <= 25:
        return 5
    if duration <= 35:
        return 7
    if duration <= 50:
        return 9
    return 11


def variant_angle(output_index: int) -> str:
    angles = [
        "mở đầu bằng nhu cầu sử dụng thực tế",
        "nhấn vào cảm giác tiện lợi khi dùng hằng ngày",
        "đi từ vấn đề của người mua đến lợi ích sản phẩm",
        "review nhanh các điểm đáng chú ý",
        "tập trung vào tình huống dùng trong gia đình hoặc văn phòng",
    ]
    return angles[(max(1, output_index) - 1) % len(angles)]
