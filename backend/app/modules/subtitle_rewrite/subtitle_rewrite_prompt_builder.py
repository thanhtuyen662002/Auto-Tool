from __future__ import annotations

from app.modules.subtitle_quality.subtitle_quality_schema import SubtitleQualityIssue
from app.modules.subtitle_rewrite.subtitle_rewrite_schema import SubtitleRewriteStyle


STYLE_INSTRUCTIONS = {
    SubtitleRewriteStyle.short_natural: "Rut gon vua phai, tieng Viet tu nhien va de doc.",
    SubtitleRewriteStyle.very_short: "Rut gon manh, uu tien cau cuc ngan cho video nhanh.",
    SubtitleRewriteStyle.casual_tiktok: "Cau ngan, gan van noi, hop TikTok/Reels, khong lam dung slang.",
    SubtitleRewriteStyle.clear_review: "Ro nghia, de hieu, phu hop video review san pham.",
    SubtitleRewriteStyle.sales_natural: "Tu nhien, co huong ban hang nhe, tuyet doi khong them claim moi.",
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
    issue_text = "; ".join(issue.message for issue in issues) or "Cau can ngan gon va tu nhien hon."
    keywords = ", ".join(preserve_keywords) or "Khong co tu khoa bo sung."
    limit = str(max_chars) if max_chars is not None else "Khong dat gioi han cung."
    return f"""Ban la bien tap phu de tieng Viet cho video ngan.

Nhiem vu:
Viet lai cau phu de tieng Viet ngan hon, tu nhien hon va de doc hon, nhung giu nguyen y goc.

Du lieu:
- Cau tieng Trung goc: {source_text or 'Khong co'}
- Ban dich hien tai: {original_translation}
- Van de can sua: {issue_text}
- Phong cach: {style.value} - {STYLE_INSTRUCTIONS[style]}
- So goi y can tra: {suggestion_count}
- Do dai toi da: {limit}
- Tu khoa bat buoc giu nguyen: {keywords}

Quy tac bat buoc:
- Khong them y moi hoac bia thong tin san pham.
- Khong them claim nhu "tot nhat", "so 1", "100% hieu qua".
- Giu nguyen ten rieng, thuong hieu, so lieu va don vi.
- Khong doi nghia cau.
- Khong dung markdown.
- Khong giai thich dai.
- Tra JSON hop le.

Format tra ve:
{{
  "suggestions": [
    {{
      "text": "cau phu de da rut gon",
      "reason": "ly do ngan gon"
    }}
  ]
}}
"""
