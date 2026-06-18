from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubtitleCoverPlacement:
    height_ratio: float
    bottom_ratio: float
    confidence: float
    block_count: int
    source: str


def detect_subtitle_cover_from_ocr_debug(
    debug_json_path: str | None,
    *,
    fallback_height_ratio: float,
    fallback_bottom_ratio: float,
    padding_ratio: float,
    min_height_ratio: float = 0.10,
    max_height_ratio: float = 0.42,
) -> SubtitleCoverPlacement | None:
    if not debug_json_path:
        return None
    path = Path(debug_json_path)
    if not path.exists() or path.stat().st_size <= 0:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    frame_height = _positive_int(payload.get("frame_height"))
    frame_width = _positive_int(payload.get("frame_width"))
    region = _region_from(payload.get("region"))
    if not frame_height and region:
        frame_height = region["y"] + region["height"]
    if not frame_width and region:
        frame_width = region["x"] + region["width"]
    if not frame_height or not frame_width:
        return None

    bounds = _collect_text_bounds(payload, frame_width=frame_width, frame_height=frame_height)
    if not bounds:
        return None

    tops = [item[0] for item in bounds]
    bottoms = [item[1] for item in bounds]
    top = _percentile(tops, 0.10)
    bottom = _percentile(bottoms, 0.90)
    padding = max(12.0, frame_height * max(0.0, min(0.12, float(padding_ratio))))
    top = max(0.0, top - padding)
    bottom = min(float(frame_height), bottom + padding)

    min_height = frame_height * min_height_ratio
    max_height = frame_height * max_height_ratio
    if bottom - top < min_height:
        center = (top + bottom) / 2.0
        top = max(0.0, center - min_height / 2.0)
        bottom = min(float(frame_height), top + min_height)
    if bottom - top > max_height:
        center = (top + bottom) / 2.0
        top = max(0.0, center - max_height / 2.0)
        bottom = min(float(frame_height), top + max_height)

    height_ratio = max(0.01, min(0.45, (bottom - top) / frame_height))
    bottom_ratio = max(0.0, min(0.2, 1.0 - (bottom / frame_height)))
    confidence = _average_confidence(payload, bounds)
    return SubtitleCoverPlacement(
        height_ratio=round(height_ratio, 4),
        bottom_ratio=round(bottom_ratio, 4),
        confidence=round(confidence, 4),
        block_count=len(bounds),
        source="ocr_debug_blocks",
    )


def _collect_text_bounds(payload: dict[str, Any], *, frame_width: int, frame_height: int) -> list[tuple[float, float, float]]:
    bounds: list[tuple[float, float, float]] = []
    default_region = _region_from(payload.get("region"))
    for frame in payload.get("frames") or []:
        region = _region_from(frame.get("region")) or default_region
        if not region:
            continue
        for block in frame.get("raw_blocks") or []:
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            confidence = _safe_float(block.get("confidence"), 0.0)
            if confidence < 0.01 and not _contains_cjk(text):
                continue
            ys = _box_y_values(block.get("box"))
            if not ys:
                continue
            top = region["y"] + min(ys)
            bottom = region["y"] + max(ys)
            if bottom <= top:
                continue
            if bottom < 0 or top > frame_height:
                continue
            bounds.append((max(0.0, top), min(float(frame_height), bottom), confidence))
    return bounds


def _region_from(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    try:
        x = int(value.get("x", 0))
        y = int(value.get("y", 0))
        width = int(value.get("width", 0))
        height = int(value.get("height", 0))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return {"x": max(0, x), "y": max(0, y), "width": width, "height": height}


def _box_y_values(box: Any) -> list[float]:
    values: list[float] = []
    for point in box or []:
        try:
            values.append(float(point[1]))
        except Exception:
            continue
    return values


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, percentile))))
    return ordered[index]


def _average_confidence(payload: dict[str, Any], bounds: list[tuple[float, float, float]]) -> float:
    values = [item[2] for item in bounds if item[2] > 0]
    if values:
        return sum(values) / len(values)
    return _safe_float(payload.get("average_confidence"), 0.0)


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _contains_cjk(text: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in text)
