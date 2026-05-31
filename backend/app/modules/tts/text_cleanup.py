from __future__ import annotations

import re


LABEL_RE = re.compile(r"\b(?:CTA|Hook|Hashtag|Hashtags|Caption|Voiceover|Subtitle)\s*:\s*", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HASHTAG_RE = re.compile(r"(?<!\w)#[\wÀ-ỹ_]+", re.UNICODE)
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


def clean_text_for_tts(text: str) -> str:
    cleaned = str(text or "")
    cleaned = MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", cleaned)
    cleaned = LABEL_RE.sub("", cleaned)
    cleaned = HASHTAG_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[*_~>#]+", " ", cleaned)
    cleaned = EMOJI_RE.sub(" ", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"[|•·●]+", " ", cleaned)
    cleaned = re.sub(r"[^\w\sÀ-ỹ.,!?;:()%+\\/-]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -–—\t\r\n")


def estimate_voice_duration(text: str, language: str = "vi") -> float:
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        return 0.0
    chars_per_second = 12.5 if language.strip().lower().startswith("vi") else 14.0
    return round(len(cleaned) / chars_per_second, 3)
