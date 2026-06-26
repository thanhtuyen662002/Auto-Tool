from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks


NOISE_PHRASES = {
    "\u55ef",
    "\u554a",
    "\u54e6",
    "\u8d70",
    "\u8d70\u8d70\u8d70",
    "\u7535\u5f71",
    "\u5f71\u7247",
    "\u51cf\u80a5",
    "\u300a\u7535\u5f71\u300b",
    "\u300a\u5f71\u7247\u300b",
    "a",
    "ah",
    "uh",
    "um",
    "di",
    "di di di",
    "phim",
    "giam can",
    "movie",
    "film",
}

SHORT_NOISE_PATTERNS = {
    "a nay",
    "beo qua",
    "giam can",
    "qua doi",
    "tra hoa cuc",
}

ASR_NO_SPEECH_THRESHOLD = 0.60
ASR_LOG_PROB_THRESHOLD = -1.0
ASR_COMPRESSION_RATIO_THRESHOLD = 2.4


@dataclass(frozen=True)
class SubtitleQualityResult:
    ok: bool
    score: float
    reasons: list[str]
    stats: dict[str, Any]


def evaluate_srt_quality(
    srt_path: str | Path,
    *,
    source_type: str,
    video_duration: float | None = None,
    ocr_confidence: float | None = None,
    min_blocks: int | None = None,
    min_chars: int | None = None,
    min_coverage: float | None = None,
) -> SubtitleQualityResult:
    """Conservative gate for ASR/OCR subtitles before translation/rendering."""

    reasons: list[str] = []
    try:
        blocks = parse_srt_blocks(str(srt_path))
    except Exception as exc:
        return SubtitleQualityResult(
            ok=False,
            score=0.0,
            reasons=["parse_failed"],
            stats={"error": str(exc), "source_type": source_type},
        )
    if not blocks:
        return SubtitleQualityResult(ok=False, score=0.0, reasons=["empty_srt"], stats={"source_type": source_type})

    normalized_source = str(source_type or "").strip().lower()
    duration = _safe_duration(video_duration)
    required_blocks = min_blocks if min_blocks is not None else _default_min_blocks(normalized_source, duration)
    required_chars = min_chars if min_chars is not None else _default_min_chars(normalized_source, duration)
    required_coverage = min_coverage if min_coverage is not None else _default_min_coverage(normalized_source, duration)

    texts = [block.text.strip() for block in blocks if block.text.strip()]
    meaningful_chars = sum(_meaningful_char_count(text) for text in texts)
    total_subtitle_duration = _subtitle_duration(blocks)
    coverage = (total_subtitle_duration / duration) if duration else None
    noise_count = sum(1 for text in texts if _is_noise_text(text))
    short_count = sum(1 for text in texts if _meaningful_char_count(text) < 4)
    repeated_count = sum(1 for text in texts if has_repetitive_text(text))
    unique_tokens = set()
    total_tokens = 0
    for text in texts:
        tokens = _tokens(text)
        unique_tokens.update(tokens)
        total_tokens += len(tokens)
    unique_ratio = (len(unique_tokens) / total_tokens) if total_tokens else 0.0

    if len(blocks) < required_blocks:
        # Nếu số lượng blocks ít nhưng tổng số ký tự có nghĩa lớn (>= 24 ký tự)
        # và độ phủ lớn (>= 0.35) thì vẫn chấp nhận vì đó là câu thoại dài liên tục.
        is_high_quality_single_span = (
            meaningful_chars >= 24
            and coverage is not None
            and coverage >= 0.35
        )
        if not is_high_quality_single_span:
            reasons.append("too_few_blocks")
    if meaningful_chars < required_chars:
        reasons.append("too_few_meaningful_chars")
    if coverage is not None and coverage < required_coverage:
        reasons.append("low_coverage")
    if noise_count and noise_count / max(1, len(texts)) >= 0.45:
        reasons.append("noise_phrase")
    if repeated_count and repeated_count / max(1, len(texts)) >= 0.35:
        reasons.append("repetitive_text")
    if short_count == len(texts):
        reasons.append("all_segments_too_short")
    if len(blocks) >= 3 and unique_ratio < 0.35:
        reasons.append("low_text_diversity")
    if ocr_confidence is not None and normalized_source == "ocr_hardsub" and float(ocr_confidence) < 0.50:
        reasons.append("low_ocr_confidence")
    if _mostly_symbols_or_numbers(" ".join(texts)):
        reasons.append("mostly_symbols_or_numbers")

    score = 1.0
    score -= 0.18 * max(0, required_blocks - len(blocks))
    score -= 0.25 if meaningful_chars < required_chars else 0.0
    score -= 0.25 if coverage is not None and coverage < required_coverage else 0.0
    score -= 0.20 * min(1.0, noise_count / max(1, len(texts)))
    score -= 0.20 * min(1.0, repeated_count / max(1, len(texts)))
    score = round(max(0.0, min(1.0, score)), 4)

    stats = {
        "source_type": normalized_source,
        "blocks": len(blocks),
        "meaningful_chars": meaningful_chars,
        "subtitle_duration": round(total_subtitle_duration, 3),
        "video_duration": duration,
        "coverage": round(coverage, 4) if coverage is not None else None,
        "noise_count": noise_count,
        "short_count": short_count,
        "repeated_count": repeated_count,
        "unique_token_ratio": round(unique_ratio, 4),
        "ocr_confidence": ocr_confidence,
        "min_blocks": required_blocks,
        "min_chars": required_chars,
        "min_coverage": required_coverage,
    }
    return SubtitleQualityResult(ok=not reasons, score=score, reasons=reasons, stats=stats)


def segment_is_low_quality(
    text: str,
    *,
    no_speech_prob: float | None = None,
    avg_logprob: float | None = None,
    compression_ratio: float | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    meaningful_chars = _meaningful_char_count(text)
    if meaningful_chars < 2:
        reasons.append("too_short")
    if _is_noise_text(text):
        reasons.append("noise_phrase")
    if has_repetitive_text(text):
        reasons.append("repetitive_text")
    if _mostly_symbols_or_numbers(text):
        reasons.append("mostly_symbols_or_numbers")
    if no_speech_prob is not None and float(no_speech_prob) > ASR_NO_SPEECH_THRESHOLD:
        reasons.append("high_no_speech_prob")
    if avg_logprob is not None and float(avg_logprob) < ASR_LOG_PROB_THRESHOLD:
        reasons.append("low_avg_logprob")
    if compression_ratio is not None and float(compression_ratio) > ASR_COMPRESSION_RATIO_THRESHOLD:
        reasons.append("high_compression_ratio")
    return bool(reasons), reasons


def has_repetitive_text(text: str) -> bool:
    compact = _normalize_text(text).replace(" ", "")
    if len(compact) >= 3 and len(set(compact)) <= 2:
        return True
    tokens = _tokens(text)
    if len(tokens) >= 3 and len(set(tokens)) <= 1:
        return True
    if len(tokens) >= 4:
        most_common = max(tokens.count(token) for token in set(tokens))
        return most_common / len(tokens) >= 0.65
    return False


def _default_min_blocks(source_type: str, video_duration: float | None) -> int:
    if source_type == "asr":
        return 3 if (video_duration or 0) > 8 else 2
    if source_type == "ocr_hardsub":
        return 3 if (video_duration or 0) > 12 else 2
    return 1


def _default_min_chars(source_type: str, video_duration: float | None) -> int:
    if source_type == "asr":
        return 30 if (video_duration or 0) > 20 else 24
    if source_type == "ocr_hardsub":
        return 24 if (video_duration or 0) > 12 else 16
    return 8


def _default_min_coverage(source_type: str, video_duration: float | None) -> float:
    if not video_duration or video_duration <= 6:
        return 0.0
    if source_type == "ocr_hardsub":
        return 0.16
    if source_type == "asr":
        return 0.18
    return 0.0


def _subtitle_duration(blocks: list[SubtitleBlock]) -> float:
    return sum(max(0.0, float(block.end) - float(block.start)) for block in blocks)


def _safe_duration(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


def _meaningful_char_count(text: str) -> int:
    return sum(1 for char in text if char.isalpha() or _is_cjk(char))


def _tokens(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return re.findall(r"[\w\u4e00-\u9fff]+", normalized, flags=re.UNICODE)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    normalized = normalized.replace("\u0111", "d")
    normalized = "".join(char for char in unicodedata.normalize("NFD", normalized) if unicodedata.category(char) != "Mn")
    normalized = re.sub(r"[^\w\s\u4e00-\u9fff]+", " ", normalized, flags=re.UNICODE)
    return re.sub(r"\s+", " ", normalized).strip()


def _is_noise_text(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return True
    compact = normalized.replace(" ", "")
    if normalized in NOISE_PHRASES or compact in NOISE_PHRASES:
        return True
    token_count = len(_tokens(normalized))
    return token_count <= 5 and any(pattern in normalized for pattern in SHORT_NOISE_PATTERNS)


def _mostly_symbols_or_numbers(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return True
    meaningful = _meaningful_char_count(raw)
    digits = sum(1 for char in raw if char.isdigit())
    visible = sum(1 for char in raw if not char.isspace())
    if visible == 0:
        return True
    return meaningful <= 1 and (digits / visible >= 0.5 or visible <= 4)


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"
