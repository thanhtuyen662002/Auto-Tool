from __future__ import annotations

from app.modules.script_variants.variant_schema import ScriptVariantRequest, ScriptVariantStyle


def build_script_variant_prompt(request: ScriptVariantRequest, style: ScriptVariantStyle) -> str:
    features = "\n".join(f"- {feature}" for feature in request.product.features)
    specs = _format_specs(getattr(request.product, "specs", []))
    product_warnings = _format_product_warnings(getattr(request.product, "validation_warnings", []))
    timeline_template_id = request.timeline_template_id or "ugc_reviewer_natural"
    industry_context = _industry_context(request)
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

ThÃ´ng sá»‘ Ä‘Æ°á»£c cung cáº¥p:
{specs}

{product_warnings}

CTA gốc:
{request.product.cta}

Thông tin video:
- Thời lượng: {request.render_duration:g} giây
- Timeline style: {timeline_template_id}
- Variant style: {request.variant_style_id}
- Hook type: {style.hook_type}
- Tone: {style.tone}
- CTA style: {style.cta_style}
- Chá»‰ Ä‘Æ°á»£c dÃ¹ng specs cÃ³ trong danh sÃ¡ch "ThÃ´ng sá»‘ Ä‘Æ°á»£c cung cáº¥p"
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
""".strip() + (f"\n\n{industry_context}" if industry_context else "")


def _format_specs(specs) -> str:
    items = []
    for spec in specs or []:
        name = getattr(spec, "name", "")
        value = getattr(spec, "value", "")
        if name and value:
            items.append(f"- {name}: {value}")
    return "\n".join(items) if items else "- KhÃ´ng cÃ³ thÃ´ng sá»‘ cá»¥ thá»ƒ Ä‘Æ°á»£c cung cáº¥p."


def _format_product_warnings(warnings: list[str]) -> str:
    cleaned = [" ".join(str(item).split()) for item in warnings if str(item).strip()]
    if not cleaned:
        return ""
    lines = "\n".join(f"- {item}" for item in cleaned[:6])
    return f"""Cáº£nh bÃ¡o ná»™i dung:
{lines}
"""


def _industry_context(request: ScriptVariantRequest) -> str:
    if not request.industry_preset_id:
        return ""
    hashtags = ", ".join(request.hashtag_suggestions)
    preferred = ", ".join(request.preferred_script_variant_ids)
    notes = "\n".join(f"- {note}" for note in request.industry_notes) or "- Không tạo claim sai sự thật theo ngành hàng."
    return f"""
Ngành hàng:
{request.industry_name or request.industry_preset_id}

Caption tone:
{request.caption_tone or ""}

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
