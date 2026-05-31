from __future__ import annotations


def build_product_video_script_prompt(product, render_settings, ai_settings, output_index: int = 1) -> str:
    features = "\n".join(f"- {feature}" for feature in product.features)
    duration = float(render_settings.duration)
    line_count = recommended_line_count(duration)
    angle = variant_angle(output_index)
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

CTA:
{product.cta}

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
