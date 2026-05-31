from __future__ import annotations

from app.modules.script_variants.variant_schema import ScriptVariantRequest, ScriptVariantStyle


def build_script_variant_prompt(request: ScriptVariantRequest, style: ScriptVariantStyle) -> str:
    features = "\n".join(f"- {feature}" for feature in request.product.features)
    timeline_template_id = request.timeline_template_id or "ugc_reviewer_natural"
    return f"""
Bạn là chuyên gia viết kịch bản video quảng cáo ngắn cho TikTok/Shopee/Reels tại Việt Nam.

Hãy viết biến thể kịch bản số {request.output_index}/{request.total_outputs} cho sản phẩm sau:

Tên sản phẩm:
{request.product.name}

Thương hiệu:
{request.product.brand}

Mô tả:
{request.product.description}

Điểm nổi bật được phép dùng:
{features}

CTA gốc:
{request.product.cta}

Thông tin video:
- Thời lượng: {request.render_duration:g} giây
- Timeline style: {timeline_template_id}
- Variant style: {request.variant_style_id}
- Hook type: {style.hook_type}
- Tone: {style.tone}
- CTA style: {style.cta_style}
- Ngôn ngữ: {request.language}

Quy tắc bắt buộc:
- Chỉ dùng thông tin sản phẩm được cung cấp
- Không bịa thêm thông số kỹ thuật
- Không dùng claim tuyệt đối như "tốt nhất", "số 1", "100% hiệu quả" nếu không có dữ liệu
- Không nói quá công dụng
- Không nhắc đến việc reup, remix, né bản quyền hoặc thuật toán
- Không dùng từ gây spam quá mức
- Câu ngắn, tự nhiên như người Việt nói
- Voiceover chia 3 đến 5 đoạn
- Voiceover phải phủ gần đủ thời lượng video
- Subtitle mỗi dòng tối đa 12 từ
- Caption ngắn, dùng được khi đăng bài
- Hashtag 3 đến 6 hashtag
- Trả về JSON hợp lệ duy nhất, không markdown, không giải thích

Schema JSON bắt buộc:

{{
  "variant_style_id": "{request.variant_style_id}",
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
