from __future__ import annotations

from app.modules.subtitle_quality.subtitle_quality_schema import SubtitleQualityIssue
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import SubtitleRewriteStyle


STYLE_INSTRUCTIONS = {
    SubtitleRewriteStyle.short_natural: "Rút gọn vừa phải, tiếng Việt tự nhiên và dễ đọc.",
    SubtitleRewriteStyle.very_short: "Rút gọn mạnh, ưu tiên câu cực ngắn cho video nhanh.",
    SubtitleRewriteStyle.casual_tiktok: "Câu ngắn, gần văn nói, hợp TikTok/Reels, không lạm dụng slang.",
    SubtitleRewriteStyle.clear_review: "Rõ nghĩa, dễ hiểu, phù hợp video review sản phẩm.",
    SubtitleRewriteStyle.sales_natural: "Tự nhiên, có hướng bán hàng nhẹ, tuyệt đối không thêm claim mới.",
}


def build_subtitle_rewrite_prompt(
    source_text: str | None,
    original_translation: str,
    issues: list[SubtitleQualityIssue],
    style: SubtitleRewriteStyle,
    suggestion_count: int,
    max_chars: int | None,
    preserve_keywords: list[str],
) -> str:
    issue_text = "; ".join(issue.message for issue in issues) or "Câu cần ngắn gọn và tự nhiên hơn."
    keywords = ", ".join(preserve_keywords) or "Không có từ khóa bổ sung."
    limit = str(max_chars) if max_chars is not None else "Không đặt giới hạn cứng."
    return f"""Bạn là biên tập phụ đề tiếng Việt cho video ngắn.

Nhiệm vụ:
Viết lại câu phụ đề tiếng Việt ngắn hơn, tự nhiên hơn và dễ đọc hơn, nhưng giữ nguyên ý gốc.

Dữ liệu:
- Câu tiếng Trung gốc: {source_text or 'Không có'}
- Bản dịch hiện tại: {original_translation}
- Vấn đề cần sửa: {issue_text}
- Phong cách: {style.value} - {STYLE_INSTRUCTIONS[style]}
- Số gợi ý cần trả: {suggestion_count}
- Độ dài tối đa: {limit}
- Từ khóa bắt buộc giữ nguyên: {keywords}

Quy tắc bắt buộc:
- Không thêm ý mới hoặc bịa thông tin sản phẩm.
- Không thêm claim như "tốt nhất", "số 1", "100% hiệu quả".
- Giữ nguyên tên riêng, thương hiệu, số liệu và đơn vị.
- Không đổi nghĩa câu.
- Không dùng markdown.
- Không giải thích dài.
- Trả JSON hợp lệ.

Format trả về:
{{
  "suggestions": [
    {{
      "text": "câu phụ đề đã rút gọn",
      "reason": "lý do ngắn gọn"
    }}
  ]
}}
"""
