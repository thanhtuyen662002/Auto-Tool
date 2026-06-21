from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.chinese_text_cleaner import ChineseTextCleaner
from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRSubtitleLine


LOW_CONFIDENCE_WARNING = (
    "ocr_low_confidence_candidate: OCR confidence thấp hơn ngưỡng cấu hình nhưng text có đủ chữ Trung; "
    "hãy review kỹ dòng này."
)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
WATERMARK_FILTER_WARNING = "ocr_watermark_filtered: removed an OCR watermark/channel label before subtitle translation."
DEFAULT_WATERMARK_TERMS = ("\u5c0f\u7c73\u540c\u5b66", "\u5c0f\u7c73\u540c\u5b78")


class OCRLineMerger:
    def __init__(self, cleaner: ChineseTextCleaner | None = None) -> None:
        self.cleaner = cleaner or ChineseTextCleaner()
        self.last_filter_summary: dict[str, Any] = {}

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

        self.last_filter_summary = {
            "watermark_removed_frame_count": 0,
            "watermark_only_frame_count": 0,
            "auto_watermark_terms_count": 0,
            "auto_watermark_terms": [],
        }
        auto_watermark_terms = _detect_auto_watermark_terms(frame_results, settings, self.cleaner)
        self.last_filter_summary["auto_watermark_terms_count"] = len(auto_watermark_terms)
        self.last_filter_summary["auto_watermark_terms"] = auto_watermark_terms
        candidates: list[dict] = []
        for frame in sorted(frame_results, key=lambda item: item.timestamp_ms):
            frame_text = _filtered_frame_text(frame, settings, self.cleaner, auto_watermark_terms)
            text = frame_text["text"]
            watermark_removed = bool(frame_text["watermark_removed"])
            if watermark_removed:
                self.last_filter_summary["watermark_removed_frame_count"] += 1
                if not text:
                    self.last_filter_summary["watermark_only_frame_count"] += 1
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
                    "warnings": [WATERMARK_FILTER_WARNING] if watermark_removed else [],
                }
            )

        lines: list[OCRSubtitleLine] = []
        current: dict | None = None
        for candidate in candidates:
            timestamp_ms = int(candidate["timestamp_ms"])
            text = str(candidate["text"])
            confidence = float(candidate["confidence"])
            is_low_confidence = bool(candidate["is_low_confidence"])
            candidate_warnings = list(candidate.get("warnings") or [])
            if current is None:
                current = _new_line(timestamp_ms, text, confidence, is_low_confidence, candidate_warnings)
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
                for warning in candidate_warnings:
                    if warning not in current["warnings"]:
                        current["warnings"].append(warning)
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
            current = _new_line(timestamp_ms, text, confidence, is_low_confidence, candidate_warnings)

        if current is not None:
            lines.append(_close_line(current, len(lines) + 1, min_duration, max_duration))
        return lines


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _new_line(
    timestamp_ms: int,
    text: str,
    confidence: float,
    is_low_confidence: bool = False,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "start_ms": int(timestamp_ms),
        "last_ts": int(timestamp_ms),
        "text": text,
        "confidences": [float(confidence)],
        "best_confidence": float(confidence),
        "is_low_confidence": bool(is_low_confidence),
        "frame_count": 1,
        "warnings": _dedupe_warnings(([LOW_CONFIDENCE_WARNING] if is_low_confidence else []) + list(warnings or [])),
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


def _filtered_frame_text(
    frame: OCRFrameResult,
    settings: DouyinReupSettings,
    cleaner: ChineseTextCleaner,
    auto_watermark_terms: list[str] | None = None,
) -> dict[str, Any]:
    if not bool(getattr(settings, "ocr_filter_watermarks", True)):
        return {"text": cleaner.clean(frame.text), "watermark_removed": False}

    raw_result = _text_from_raw_blocks(frame, settings, cleaner, auto_watermark_terms or [])
    if raw_result["used_raw_blocks"]:
        return {"text": raw_result["text"], "watermark_removed": raw_result["watermark_removed"]}

    text, watermark_removed = _strip_watermark_terms(cleaner.clean(frame.text), settings, auto_watermark_terms)
    return {"text": cleaner.clean(text), "watermark_removed": watermark_removed}


def _text_from_raw_blocks(
    frame: OCRFrameResult,
    settings: DouyinReupSettings,
    cleaner: ChineseTextCleaner,
    auto_watermark_terms: list[str] | None = None,
) -> dict[str, Any]:
    raw_blocks = list(frame.raw_blocks or [])
    if not raw_blocks:
        return {"text": "", "watermark_removed": False, "used_raw_blocks": False}

    blocks: list[dict[str, Any]] = []
    watermark_removed = False
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            continue
        text, removed = _strip_watermark_terms(cleaner.clean(raw.get("text", "")), settings, auto_watermark_terms)
        watermark_removed = watermark_removed or removed
        text = cleaner.clean(text)
        if not text:
            continue
        bounds = _raw_block_bounds(raw)
        blocks.append(
            {
                "text": text,
                "confidence": _safe_float(raw.get("confidence"), float(frame.confidence)),
                "left": bounds[0] if bounds else None,
                "top": bounds[1] if bounds else None,
                "right": bounds[2] if bounds else None,
                "bottom": bounds[3] if bounds else None,
            }
        )

    if not blocks:
        return {"text": "", "watermark_removed": watermark_removed, "used_raw_blocks": watermark_removed}

    selected = _select_subtitle_blocks(blocks, width=max(1, frame.region.width), height=max(1, frame.region.height))
    text = cleaner.clean(" ".join(block["text"] for block in _sort_blocks_for_reading(selected)))
    return {"text": text, "watermark_removed": watermark_removed, "used_raw_blocks": True}


def _strip_watermark_terms(
    text: str,
    settings: DouyinReupSettings,
    auto_watermark_terms: list[str] | None = None,
) -> tuple[str, bool]:
    output = str(text or "")
    removed = False
    for term in _watermark_terms(settings, auto_watermark_terms):
        pattern = _watermark_pattern(term)
        if not pattern:
            continue
        next_output = re.sub(pattern, " ", output, flags=re.IGNORECASE)
        if next_output != output:
            output = next_output
            removed = True
    return re.sub(r"\s+", " ", output).strip(), removed


def _watermark_terms(settings: DouyinReupSettings, auto_watermark_terms: list[str] | None = None) -> list[str]:
    raw_terms = getattr(settings, "ocr_watermark_terms", None)
    terms = [*DEFAULT_WATERMARK_TERMS, *(raw_terms or []), *(auto_watermark_terms or [])]
    cleaned: list[str] = []
    seen: set[str] = set()
    for term in terms:
        text = re.sub(r"\s+", "", str(term or ""))
        if not text:
            continue
        key = _normalize_for_similarity(text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _watermark_pattern(term: str) -> str:
    compact = [char for char in str(term or "") if not char.isspace()]
    if not compact:
        return ""
    separator = r"[\s\-_.:：·•|/\\]*"
    return separator.join(re.escape(char) for char in compact)


def _detect_auto_watermark_terms(
    frame_results: list[OCRFrameResult],
    settings: DouyinReupSettings,
    cleaner: ChineseTextCleaner,
) -> list[str]:
    if not bool(getattr(settings, "ocr_filter_watermarks", True)):
        return []

    stats: dict[str, dict[str, Any]] = {}
    text_frame_count = 0

    for frame in frame_results:
        frame_terms: set[str] = set()
        raw_compacts: list[str] = []
        raw_terms: set[str] = set()

        for raw in frame.raw_blocks or []:
            if not isinstance(raw, dict):
                continue
            raw_text = cleaner.clean(raw.get("text", ""))
            compact = _normalize_for_similarity(raw_text)
            if not compact:
                continue
            raw_compacts.append(compact)
            if _is_plausible_auto_watermark_term(compact):
                raw_terms.add(compact)

        for term in raw_terms:
            context = " ".join(sorted(item for item in raw_compacts if item != term))
            _remember_auto_term(stats, term, frame.timestamp_ms, context=context, raw_block=True)
            frame_terms.add(term)

        compact_text = _normalize_for_similarity(cleaner.clean(frame.text))
        if compact_text:
            text_frame_count += 1
            for term in _edge_auto_watermark_candidates(compact_text):
                context = compact_text.replace(term, "", 1).strip()
                _remember_auto_term(stats, term, frame.timestamp_ms, context=context, raw_block=False)
                frame_terms.add(term)

        for term in frame_terms:
            stats[term]["frame_hits"].add(int(frame.timestamp_ms))

    frame_floor = max(3, int(max(1, text_frame_count) * 0.35 + 0.999))
    selected: list[str] = []
    for term, item in stats.items():
        frame_hits = len(item.get("frame_hits") or set())
        contexts = {context for context in item.get("contexts", set()) if context}
        raw_hits = int(item.get("raw_hits", 0) or 0)
        if frame_hits < frame_floor and raw_hits < frame_floor:
            continue
        if len(contexts) < 2:
            continue
        selected.append(term)

    selected = sorted(selected, key=lambda value: (-len(value), value))
    filtered: list[str] = []
    for term in selected:
        if any(term in existing for existing in filtered):
            continue
        filtered.append(term)
    return filtered[:12]


def _remember_auto_term(
    stats: dict[str, dict[str, Any]],
    term: str,
    timestamp_ms: int,
    *,
    context: str,
    raw_block: bool,
) -> None:
    if not _is_plausible_auto_watermark_term(term):
        return
    item = stats.setdefault(term, {"frame_hits": set(), "contexts": set(), "raw_hits": 0})
    item["frame_hits"].add(int(timestamp_ms))
    if context and context != term:
        item["contexts"].add(context)
    if raw_block:
        item["raw_hits"] = int(item.get("raw_hits", 0) or 0) + 1


def _edge_auto_watermark_candidates(compact_text: str) -> set[str]:
    compact = _normalize_for_similarity(compact_text)
    if len(compact) < 7:
        return set()
    candidates: set[str] = set()
    max_len = min(12, max(3, len(compact) - 3))
    for length in range(3, max_len + 1):
        prefix = compact[:length]
        suffix = compact[-length:]
        if _is_plausible_auto_watermark_term(prefix):
            candidates.add(prefix)
        if _is_plausible_auto_watermark_term(suffix):
            candidates.add(suffix)
    return candidates


def _is_plausible_auto_watermark_term(text: str) -> bool:
    compact = _normalize_for_similarity(text)
    length = len(compact)
    if length < 3 or length > 16:
        return False
    cjk_count = len(CJK_RE.findall(compact))
    ascii_count = sum(1 for char in compact if char.isascii() and char.isalnum())
    if cjk_count >= 2:
        return True
    return ascii_count >= 4


def _raw_block_bounds(raw: dict[str, Any]) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for point in raw.get("box") or []:
        try:
            xs.append(float(point[0]))
            ys.append(float(point[1]))
        except Exception:
            continue
    if not xs or not ys:
        return None
    left = min(xs)
    right = max(xs)
    top = min(ys)
    bottom = max(ys)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _select_subtitle_blocks(blocks: list[dict[str, Any]], *, width: int, height: int) -> list[dict[str, Any]]:
    boxed = [block for block in blocks if block.get("left") is not None]
    if not boxed:
        return blocks

    candidates: list[dict[str, Any]] = []
    for block in boxed:
        width_ratio = (float(block["right"]) - float(block["left"])) / max(1.0, float(width))
        center_x = ((float(block["left"]) + float(block["right"])) / 2.0) / max(1.0, float(width))
        visible_length = _visible_text_length(str(block["text"]))
        if visible_length <= 2 and width_ratio < 0.22:
            continue
        if visible_length <= 4 and width_ratio < 0.16 and _center_score(center_x) < 0.65:
            continue
        candidates.append(block)

    clusters = _cluster_blocks_by_y(candidates or boxed, height=height)
    if not clusters:
        return blocks
    return max(clusters, key=lambda cluster: _cluster_score(cluster, width=width, height=height))


def _cluster_blocks_by_y(blocks: list[dict[str, Any]], *, height: int) -> list[list[dict[str, Any]]]:
    max_gap = max(18.0, float(height) * 0.12)
    clusters: list[list[dict[str, Any]]] = []
    for block in sorted(blocks, key=lambda item: (float(item["top"]), float(item["left"]))):
        if not clusters:
            clusters.append([block])
            continue
        current = clusters[-1]
        current_bottom = max(float(item["bottom"]) for item in current)
        if float(block["top"]) <= current_bottom + max_gap:
            current.append(block)
        else:
            clusters.append([block])
    return clusters


def _cluster_score(cluster: list[dict[str, Any]], *, width: int, height: int) -> float:
    left = min(float(block["left"]) for block in cluster)
    right = max(float(block["right"]) for block in cluster)
    top = min(float(block["top"]) for block in cluster)
    bottom = max(float(block["bottom"]) for block in cluster)
    width_ratio = (right - left) / max(1.0, float(width))
    center_x = ((left + right) / 2.0) / max(1.0, float(width))
    center_y = ((top + bottom) / 2.0) / max(1.0, float(height))
    text_length = sum(_visible_text_length(str(block["text"])) for block in cluster)
    confidence = _average([float(block["confidence"]) for block in cluster if float(block["confidence"]) > 0])
    score = (
        len(cluster) * 0.35
        + confidence * 1.2
        + min(1.0, width_ratio) * 3.0
        + min(1.6, text_length / 10.0)
        + _center_score(center_x) * 1.4
    )
    if 0.35 <= center_y <= 0.86:
        score += 0.6
    if center_y >= 0.92 and width_ratio < 0.45:
        score -= 1.8
    if center_y <= 0.18 and width_ratio < 0.28:
        score -= 1.1
    return score


def _sort_blocks_for_reading(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        blocks,
        key=lambda block: (
            float(block["top"]) if block.get("top") is not None else 0.0,
            float(block["left"]) if block.get("left") is not None else 0.0,
        ),
    )


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _visible_text_length(text: str) -> int:
    return sum(1 for char in str(text or "") if char.isalnum() or CJK_RE.match(char))


def _center_score(center_x_ratio: float) -> float:
    return max(0.0, 1.0 - abs(float(center_x_ratio) - 0.5) * 2.0)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _dedupe_warnings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


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
