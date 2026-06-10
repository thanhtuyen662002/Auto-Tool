from __future__ import annotations

import re
import unicodedata

from app.modules.subtitle_quality.subtitle_quality_rules import CJK_RE, MARKDOWN_OR_JSON_RE


FORBIDDEN_CLAIMS = (
    "tốt nhất",
    "số 1",
    "100%",
    "cam kết hiệu quả",
    "khỏi hẳn",
    "trị dứt điểm",
    "giảm cân thần tốc",
    "trắng bật tông",
    "an toàn tuyệt đối",
    "không tác dụng phụ",
)

NUMBER_UNIT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|kg|mg|g|ml|l|cm|mm|km|m|vnd|usd|đ|đồng|giây|phút|giờ)?",
    re.IGNORECASE,
)


class SubtitleRewriteValidator:
    def validate_suggestion(
        self,
        source_text: str | None,
        original_translation: str,
        suggested_text: str,
        preserve_keywords: list[str],
    ) -> tuple[bool, list[str]]:
        del source_text
        warnings: list[str] = []
        original = original_translation.strip()
        suggested = suggested_text.strip()

        if not suggested:
            warnings.append("critical: Suggested text is empty.")
            return False, warnings
        if original and len(suggested) > max(1, int(len(original) * 1.1)):
            warnings.append("warning: Suggestion is more than 10% longer than the original translation.")
        if MARKDOWN_OR_JSON_RE.search(suggested):
            warnings.append("critical: Suggestion contains markdown or JSON content.")
        if len(CJK_RE.findall(suggested)) >= 3:
            warnings.append("critical: Suggestion still contains too many Chinese characters.")

        normalized = suggested.casefold()
        normalized_claim_text = _normalize_claim_text(suggested)
        for keyword in preserve_keywords:
            if keyword.casefold() not in normalized:
                warnings.append(f'critical: Required keyword is missing: "{keyword}".')

        original_numbers = _important_numbers(original)
        suggested_numbers = _important_numbers(suggested)
        for token in original_numbers:
            if token not in suggested_numbers:
                warnings.append(f'critical: Original number or unit is missing: "{token}".')

        for claim in FORBIDDEN_CLAIMS:
            if _normalize_claim_text(claim) in normalized_claim_text:
                warnings.append(f'critical: Forbidden claim detected: "{claim}".')

        return not warnings, list(dict.fromkeys(warnings))


def _important_numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", match.group(0).casefold()) for match in NUMBER_UNIT_RE.finditer(text)}


def _normalize_claim_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_marks).strip()
