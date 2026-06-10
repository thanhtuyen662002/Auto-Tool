from __future__ import annotations

from difflib import SequenceMatcher

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.chinese_text_cleaner import ChineseTextCleaner
from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRSubtitleLine


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

        candidates: list[tuple[int, str, float]] = []
        for frame in sorted(frame_results, key=lambda item: item.timestamp_ms):
            text = self.cleaner.clean(frame.text)
            if frame.confidence < min_confidence:
                continue
            if not self.cleaner.looks_like_chinese_subtitle(text, min_text_length=min_text_length):
                continue
            candidates.append((frame.timestamp_ms, text, frame.confidence))

        lines: list[OCRSubtitleLine] = []
        current: dict | None = None
        for timestamp_ms, text, confidence in candidates:
            if current is None:
                current = _new_line(timestamp_ms, text, confidence)
                continue

            gap = timestamp_ms - int(current["last_ts"])
            if similarity(str(current["text"]), text) >= threshold and gap <= max(max_gap, min_duration * 2):
                current["last_ts"] = timestamp_ms
                current["confidences"].append(confidence)
                current["frame_count"] += 1
                if len(text) > len(str(current["text"])):
                    current["text"] = text
                continue

            lines.append(_close_line(current, len(lines) + 1, min_duration, max_duration))
            current = _new_line(timestamp_ms, text, confidence)

        if current is not None:
            lines.append(_close_line(current, len(lines) + 1, min_duration, max_duration))
        return lines


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _new_line(timestamp_ms: int, text: str, confidence: float) -> dict:
    return {
        "start_ms": int(timestamp_ms),
        "last_ts": int(timestamp_ms),
        "text": text,
        "confidences": [float(confidence)],
        "frame_count": 1,
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
    )
