from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.chinese_text_cleaner import ChineseTextCleaner
from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRSubtitleLine


LOW_CONFIDENCE_WARNING = (
    "ocr_low_confidence_candidate: OCR confidence thấp hơn ngưỡng cấu hình nhưng text có đủ chữ Trung; "
    "hãy review kỹ dòng này."
)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class OCRLineMerger:
    def __init__(self, cleaner: ChineseTextCleaner | None = None) -> None:
        self.cleaner = cleaner or ChineseTextCleaner()

    def merge_frames_to_lines(
        self,
        frame_results: list[OCRFrameResult],
        settings: DouyinReupSettings,
    ) -> list[OCRSubtitleLine]:
        min_confidence = float(settings.ocr_min_confidence)
        min_text_length = int(settings.ocr_min_text_length)
        threshold = float(settings.ocr_dedupe_similarity)
        max_gap = int(settings.ocr_merge_gap_ms)
        min_duration = int(settings.ocr_min_duration_ms)
        max_duration = int(settings.ocr_max_duration_ms)

        candidates: list[dict] = []
        for frame in sorted(frame_results, key=lambda item: item.timestamp_ms):
            text = self.cleaner.clean(frame.text)
            if not self.cleaner.looks_like_chinese_subtitle(text, min_text_length=min_text_length):
                continue
            confidence = float(frame.confidence)
            is_low_confidence = confidence < min_confidence
            if is_low_confidence and not _accept_low_confidence_candidate(
                text,
                confidence=confidence,
                min_confidence=min_confidence,
                min_text_length=min_text_length,
            ):
                continue
            candidates.append(
                {
                    "timestamp_ms": int(frame.timestamp_ms),
                    "text": text,
                    "confidence": confidence,
                    "is_low_confidence": is_low_confidence,
                }
            )

        lines: list[OCRSubtitleLine] = []
        current: dict | None = None
        for candidate in candidates:
            timestamp_ms = int(candidate["timestamp_ms"])
            text = str(candidate["text"])
            confidence = float(candidate["confidence"])
            is_low_confidence = bool(candidate["is_low_confidence"])
            if current is None:
                current = _new_line(timestamp_ms, text, confidence, is_low_confidence)
                continue

            gap = timestamp_ms - int(current["last_ts"])
            same_text_threshold = _effective_similarity_threshold(
                threshold,
                bool(current.get("is_low_confidence")) or is_low_confidence,
            )
            if _same_subtitle_text(str(current["text"]), text, same_text_threshold) and gap <= max(max_gap, min_duration * 2):
                current["last_ts"] = timestamp_ms
                current["confidences"].append(confidence)
                current["frame_count"] += 1
                current["is_low_confidence"] = bool(current.get("is_low_confidence")) or is_low_confidence
                if is_low_confidence and LOW_CONFIDENCE_WARNING not in current["warnings"]:
                    current["warnings"].append(LOW_CONFIDENCE_WARNING)
                if _is_better_text(
                    str(current["text"]),
                    float(current.get("best_confidence", 0.0)),
                    text,
                    confidence,
                ):
                    current["text"] = text
                    current["best_confidence"] = confidence
                continue

            lines.append(_close_line(current, len(lines) + 1, min_duration, max_duration))
            current = _new_line(timestamp_ms, text, confidence, is_low_confidence)

        if current is not None:
            lines.append(_close_line(current, len(lines) + 1, min_duration, max_duration))
        return lines


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _new_line(timestamp_ms: int, text: str, confidence: float, is_low_confidence: bool = False) -> dict:
    return {
        "start_ms": int(timestamp_ms),
        "last_ts": int(timestamp_ms),
        "text": text,
        "confidences": [float(confidence)],
        "best_confidence": float(confidence),
        "is_low_confidence": bool(is_low_confidence),
        "frame_count": 1,
        "warnings": [LOW_CONFIDENCE_WARNING] if is_low_confidence else [],
    }


def _close_line(current: dict, index: int, min_duration_ms: int, max_duration_ms: int) -> OCRSubtitleLine:
    start_ms = int(current["start_ms"])
    end_ms = int(current["last_ts"]) + max(1, int(min_duration_ms))
    end_ms = min(end_ms, start_ms + max(1, int(max_duration_ms)))
    if end_ms <= start_ms:
        end_ms = start_ms + max(1, int(min_duration_ms))
    confidences = [float(value) for value in current["confidences"]]
    return OCRSubtitleLine(
        index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        text=str(current["text"]),
        confidence=sum(confidences) / len(confidences),
        frame_count=int(current["frame_count"]),
        warnings=list(current.get("warnings") or []),
    )


def _accept_low_confidence_candidate(
    text: str,
    *,
    confidence: float,
    min_confidence: float,
    min_text_length: int,
) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    cjk_count = len(CJK_RE.findall(compact))
    if cjk_count < max(2, int(min_text_length)):
        return False
    cjk_ratio = cjk_count / max(1, len(compact))
    if cjk_ratio < 0.35:
        return False
    if len(compact) > 80 and cjk_ratio < 0.5:
        return False

    confidence_value = max(0.0, float(confidence))
    configured_floor = max(0.02, min(0.08, float(min_confidence) * 0.08))
    if confidence_value >= configured_floor:
        return True
    if cjk_count >= 10 and confidence_value >= 0.02:
        return True
    if cjk_count >= 5 and confidence_value >= 0.03:
        return True
    return cjk_count >= 14 and confidence_value >= 0.005


def _effective_similarity_threshold(configured_threshold: float, has_low_confidence: bool) -> float:
    threshold = max(0.0, min(1.0, float(configured_threshold)))
    if has_low_confidence:
        return min(threshold, max(0.78, threshold - 0.08))
    return threshold


def _same_subtitle_text(a: str, b: str, threshold: float) -> bool:
    left = _normalize_for_similarity(a)
    right = _normalize_for_similarity(b)
    if not left or not right:
        return False
    if similarity(left, right) >= threshold:
        return True
    return _common_substring_ratio(left, right) >= max(0.72, threshold - 0.08)


def _normalize_for_similarity(text: str) -> str:
    compact = re.sub(r"\s+", "", str(text or ""))
    return re.sub(r"[^\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaffA-Za-z0-9]", "", compact)


def _common_substring_ratio(a: str, b: str) -> float:
    shorter = min(len(a), len(b))
    if shorter <= 0:
        return 0.0
    match = SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b))
    return match.size / shorter


def _is_better_text(current_text: str, current_confidence: float, new_text: str, new_confidence: float) -> bool:
    if new_confidence >= current_confidence + 0.08:
        return True
    if current_confidence >= new_confidence + 0.08:
        return False
    current_cjk = len(CJK_RE.findall(current_text))
    new_cjk = len(CJK_RE.findall(new_text))
    if new_cjk != current_cjk:
        return new_cjk > current_cjk
    return len(new_text) > len(current_text)
