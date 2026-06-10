from __future__ import annotations

import re


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
ALLOWED_CHARS_RE = re.compile(r"[^\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9%°℃￥$.,!?;:，。！？、：；《》“”‘’（）()【】\[\]\+\-/\s]")


class ChineseTextCleaner:
    def clean(self, text: str) -> str:
        cleaned = str(text or "").replace("\r", " ").replace("\n", " ")
        cleaned = ALLOWED_CHARS_RE.sub("", cleaned)
        cleaned = re.sub(r"([\-_=~*·•])\1{2,}", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def looks_like_chinese_subtitle(self, text: str, min_text_length: int = 2) -> bool:
        cleaned = self.clean(text)
        compact = re.sub(r"\s+", "", cleaned)
        if len(compact) < max(1, int(min_text_length)):
            return False
        if not CJK_RE.search(compact):
            return False
        non_symbols = re.sub(r"[\W_]+", "", compact, flags=re.UNICODE)
        return bool(non_symbols)
