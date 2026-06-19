from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SubtitleCoverSegment:
    start: float
    end: float
    left_ratio: float
    top_ratio: float
    right_ratio: float
    bottom_edge_ratio: float
    confidence: float
    block_count: int


@dataclass(frozen=True)
class SubtitleCoverPlacement:
    height_ratio: float
    bottom_ratio: float
    confidence: float
    block_count: int
    source: str
    segments: tuple[SubtitleCoverSegment, ...] = ()


@dataclass(frozen=True)
class _BlockBounds:
    left: float
    top: float
    right: float
    bottom: float
    confidence: float
    has_cjk: bool


@dataclass(frozen=True)
class _FrameTextBounds:
    timestamp_ms: int
    left: float
    top: float
    right: float
    bottom: float
    confidence: float
    block_count: int


def detect_subtitle_cover_from_ocr_debug(
    debug_json_path: str | None,
    *,
    fallback_height_ratio: float,
    fallback_bottom_ratio: float,
    padding_ratio: float,
    min_height_ratio: float = 0.055,
    max_height_ratio: float = 0.28,
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

    frame_bounds = _collect_frame_text_bounds(payload, frame_width=frame_width, frame_height=frame_height)
    if not frame_bounds:
        return None

    _, top, _, bottom = _padded_rect(
        left=_percentile([item.left for item in frame_bounds], 0.10),
        top=_percentile([item.top for item in frame_bounds], 0.10),
        right=_percentile([item.right for item in frame_bounds], 0.90),
        bottom=_percentile([item.bottom for item in frame_bounds], 0.90),
        frame_width=frame_width,
        frame_height=frame_height,
        padding_ratio=padding_ratio,
        min_height_ratio=min_height_ratio,
        max_height_ratio=max_height_ratio,
    )

    height_ratio = max(0.01, min(0.45, (bottom - top) / frame_height))
    bottom_ratio = max(0.0, min(0.2, 1.0 - (bottom / frame_height)))
    confidence = _average_confidence(payload, [(item.top, item.bottom, item.confidence) for item in frame_bounds])
    segments = _build_timed_segments(
        frame_bounds,
        frame_width=frame_width,
        frame_height=frame_height,
        padding_ratio=padding_ratio,
        min_height_ratio=min_height_ratio,
        max_height_ratio=max_height_ratio,
    )
    return SubtitleCoverPlacement(
        height_ratio=round(height_ratio, 4),
        bottom_ratio=round(bottom_ratio, 4),
        confidence=round(confidence, 4),
        block_count=sum(item.block_count for item in frame_bounds),
        source="ocr_debug_timed_blocks" if segments else "ocr_debug_blocks",
        segments=segments,
    )


def _collect_text_bounds(payload: dict[str, Any], *, frame_width: int, frame_height: int) -> list[tuple[float, float, float]]:
    return [
        (item.top, item.bottom, item.confidence)
        for item in _collect_frame_text_bounds(payload, frame_width=frame_width, frame_height=frame_height)
    ]


def _collect_frame_text_bounds(
    payload: dict[str, Any],
    *,
    frame_width: int,
    frame_height: int,
) -> list[_FrameTextBounds]:
    frame_bounds: list[_FrameTextBounds] = []
    default_region = _region_from(payload.get("region"))
    for frame in payload.get("frames") or []:
        region = _region_from(frame.get("region")) or default_region
        if not region:
            continue
        blocks: list[_BlockBounds] = []
        for block in frame.get("raw_blocks") or []:
            parsed = _block_bounds_from_raw(block, region=region, frame_width=frame_width, frame_height=frame_height)
            if parsed:
                blocks.append(parsed)
        if not blocks:
            continue
        cjk_blocks = [block for block in blocks if block.has_cjk]
        selected = cjk_blocks or [block for block in blocks if block.confidence >= 0.15]
        cluster = _best_subtitle_cluster(selected, frame_height=frame_height)
        if not cluster:
            continue
        timestamp_ms = _safe_int(frame.get("timestamp_ms"), 0)
        confidence = _average([block.confidence for block in cluster if block.confidence > 0])
        frame_bounds.append(
            _FrameTextBounds(
                timestamp_ms=max(0, timestamp_ms),
                left=max(0.0, min(block.left for block in cluster)),
                top=max(0.0, min(block.top for block in cluster)),
                right=min(float(frame_width), max(block.right for block in cluster)),
                bottom=min(float(frame_height), max(block.bottom for block in cluster)),
                confidence=confidence,
                block_count=len(cluster),
            )
        )
    return frame_bounds


def _block_bounds_from_raw(
    block: dict[str, Any],
    *,
    region: dict[str, int],
    frame_width: int,
    frame_height: int,
) -> _BlockBounds | None:
    text = str(block.get("text") or "").strip()
    if not text:
        return None
    confidence = _safe_float(block.get("confidence"), 0.0)
    has_cjk = _contains_cjk(text)
    if confidence < 0.01 and not has_cjk:
        return None
    xs = _box_x_values(block.get("box"))
    ys = _box_y_values(block.get("box"))
    if not xs or not ys:
        return None
    left = region["x"] + min(xs)
    right = region["x"] + max(xs)
    top = region["y"] + min(ys)
    bottom = region["y"] + max(ys)
    if right <= left or bottom <= top:
        return None
    if right < 0 or left > frame_width or bottom < 0 or top > frame_height:
        return None
    block_width = right - left
    block_height = bottom - top
    if block_width < 6 or block_height < 6:
        return None
    if bottom < frame_height * 0.35:
        return None
    if block_height / frame_height > 0.18:
        return None
    return _BlockBounds(
        left=max(0.0, left),
        top=max(0.0, top),
        right=min(float(frame_width), right),
        bottom=min(float(frame_height), bottom),
        confidence=confidence,
        has_cjk=has_cjk,
    )


def _best_subtitle_cluster(blocks: list[_BlockBounds], *, frame_height: int) -> list[_BlockBounds]:
    if not blocks:
        return []
    max_gap = max(24.0, frame_height * 0.035)
    clusters: list[list[_BlockBounds]] = []
    for block in sorted(blocks, key=lambda item: (item.top, item.left)):
        if not clusters:
            clusters.append([block])
            continue
        current = clusters[-1]
        current_bottom = max(item.bottom for item in current)
        if block.top <= current_bottom + max_gap:
            current.append(block)
        else:
            clusters.append([block])
    return max(clusters, key=lambda cluster: _cluster_score(cluster, frame_height=frame_height))


def _cluster_score(cluster: list[_BlockBounds], *, frame_height: int) -> float:
    confidence = _average([block.confidence for block in cluster if block.confidence > 0])
    has_cjk = any(block.has_cjk for block in cluster)
    lower_bonus = max(block.bottom for block in cluster) / max(1.0, float(frame_height))
    text_height = sum(block.bottom - block.top for block in cluster) / max(1.0, float(frame_height))
    return (2.5 if has_cjk else 0.0) + len(cluster) * 0.35 + confidence + lower_bonus * 0.25 + min(1.0, text_height * 8.0)


def _build_timed_segments(
    frame_bounds: list[_FrameTextBounds],
    *,
    frame_width: int,
    frame_height: int,
    padding_ratio: float,
    min_height_ratio: float,
    max_height_ratio: float,
) -> tuple[SubtitleCoverSegment, ...]:
    if not frame_bounds:
        return ()
    sorted_bounds = sorted(frame_bounds, key=lambda item: item.timestamp_ms)
    intervals = _segment_intervals([item.timestamp_ms for item in sorted_bounds])
    segments: list[SubtitleCoverSegment] = []
    for item, (start, end) in zip(sorted_bounds, intervals):
        left, top, right, bottom = _padded_rect(
            left=item.left,
            top=item.top,
            right=item.right,
            bottom=item.bottom,
            frame_width=frame_width,
            frame_height=frame_height,
            padding_ratio=padding_ratio,
            min_height_ratio=min_height_ratio,
            max_height_ratio=max_height_ratio,
        )
        if end <= start:
            end = start + 0.05
        segments.append(
            SubtitleCoverSegment(
                start=round(start, 3),
                end=round(end, 3),
                left_ratio=round(left / frame_width, 4),
                top_ratio=round(top / frame_height, 4),
                right_ratio=round(right / frame_width, 4),
                bottom_edge_ratio=round(bottom / frame_height, 4),
                confidence=round(item.confidence, 4),
                block_count=item.block_count,
            )
        )
    return tuple(segments)


def _segment_intervals(timestamps_ms: list[int]) -> list[tuple[float, float]]:
    if not timestamps_ms:
        return []
    timestamps = [max(0.0, value / 1000.0) for value in timestamps_ms]
    deltas = [
        timestamps[index + 1] - timestamps[index]
        for index in range(len(timestamps) - 1)
        if timestamps[index + 1] > timestamps[index]
    ]
    default_delta = _median(deltas) if deltas else 1.0
    if default_delta <= 0:
        default_delta = 1.0
    intervals: list[tuple[float, float]] = []
    for index, timestamp in enumerate(timestamps):
        if index == 0:
            start = max(0.0, timestamp - default_delta / 2.0)
        else:
            start = (timestamps[index - 1] + timestamp) / 2.0
        if index + 1 < len(timestamps):
            end = (timestamp + timestamps[index + 1]) / 2.0
        else:
            end = timestamp + default_delta / 2.0
        intervals.append((round(start, 3), round(max(start + 0.05, end), 3)))
    return intervals


def _padded_rect(
    *,
    left: float,
    top: float,
    right: float,
    bottom: float,
    frame_width: int,
    frame_height: int,
    padding_ratio: float,
    min_height_ratio: float,
    max_height_ratio: float,
) -> tuple[float, float, float, float]:
    safe_padding = max(0.0, min(0.12, float(padding_ratio)))
    pad_y = max(8.0, min(frame_height * 0.025, frame_height * safe_padding))
    pad_x = max(18.0, min(frame_width * 0.08, frame_width * safe_padding * 1.4))
    left = max(0.0, left - pad_x)
    right = min(float(frame_width), right + pad_x)
    top = max(0.0, top - pad_y)
    bottom = min(float(frame_height), bottom + pad_y)
    top, bottom = _expand_interval(
        top,
        bottom,
        minimum=frame_height * min_height_ratio,
        maximum=frame_height * max_height_ratio,
        lower_bound=0.0,
        upper_bound=float(frame_height),
    )
    left, right = _expand_interval(
        left,
        right,
        minimum=frame_width * 0.42,
        maximum=frame_width * 0.96,
        lower_bound=0.0,
        upper_bound=float(frame_width),
    )
    return left, top, right, bottom


def _expand_interval(
    start: float,
    end: float,
    *,
    minimum: float,
    maximum: float,
    lower_bound: float,
    upper_bound: float,
) -> tuple[float, float]:
    if end - start < minimum:
        center = (start + end) / 2.0
        start = center - minimum / 2.0
        end = center + minimum / 2.0
    if end - start > maximum:
        center = (start + end) / 2.0
        start = center - maximum / 2.0
        end = center + maximum / 2.0
    if start < lower_bound:
        end = min(upper_bound, end + (lower_bound - start))
        start = lower_bound
    if end > upper_bound:
        start = max(lower_bound, start - (end - upper_bound))
        end = upper_bound
    return start, end


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


def _box_x_values(box: Any) -> list[float]:
    values: list[float] = []
    for point in box or []:
        try:
            values.append(float(point[0]))
        except Exception:
            continue
    return values


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


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _contains_cjk(text: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in text)
