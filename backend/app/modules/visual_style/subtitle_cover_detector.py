from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOTTOM_LANE_BOTTOM_RATIO = 0.78
BOTTOM_FALLBACK_HEIGHT_RATIO = 0.12
DYNAMIC_CONFIDENCE_THRESHOLD = 0.12
MIN_DYNAMIC_CJK_CONFIDENCE = 0.06
MIN_DYNAMIC_NON_CJK_CONFIDENCE = 0.2
MIN_COVER_WIDTH_RATIO = 0.88
MIN_SUBTITLE_TEXT_WIDTH_RATIO = 0.18
MAX_DYNAMIC_VERTICAL_SPAN_RATIO = 0.12
MIN_MID_SCREEN_SUBTITLE_BOTTOM_RATIO = 0.05
# pad_y tỷ lệ theo chiều cao THỰC của text block (không phải frame)
# → sub 1 dòng có pad nhỏ, sub nhiều dòng có pad lớn hơn tương xứng
_COVER_PAD_Y_TEXT_RATIO = 0.35
# Giới hạn pad_y tối thiểu/tối đa tính bằng % frame_height
_COVER_PAD_Y_MIN_RATIO = 0.005   # ≥ 0.5% frame (tránh che sát text)
_COVER_PAD_Y_MAX_RATIO = 0.018   # ≤ 1.8% frame (tránh nền che quá dày)


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
    text: str
    left: float
    top: float
    right: float
    bottom: float
    confidence: float
    has_cjk: bool


@dataclass(frozen=True)
class _FrameTextBounds:
    timestamp_ms: int
    text: str
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
    min_height_ratio: float = 0.04,
    max_height_ratio: float = 0.16,
    only_if_chinese_detected: bool = True,
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
    frame_bounds = _select_subtitle_lane(frame_bounds, frame_width=frame_width, frame_height=frame_height)
    if not frame_bounds:
        return None

    # Nếu chỉ che khi thấy chữ Trung Quốc (tránh che nhầm logo, sticker hay video sạch)
    if only_if_chinese_detected:
        has_any_chinese = any(_contains_cjk(item.text) for item in frame_bounds)
        if not has_any_chinese:
            return None

    if _should_use_bottom_fallback(frame_bounds, frame_height=frame_height):
        height_ratio = max(min_height_ratio, min(float(fallback_height_ratio), BOTTOM_FALLBACK_HEIGHT_RATIO))
        bottom_ratio = max(0.0, min(0.35, float(fallback_bottom_ratio)))
        confidence = _average_confidence(payload, [(item.top, item.bottom, item.confidence) for item in frame_bounds])
        return SubtitleCoverPlacement(
            height_ratio=round(height_ratio, 4),
            bottom_ratio=round(bottom_ratio, 4),
            confidence=round(confidence, 4),
            block_count=sum(item.block_count for item in frame_bounds),
            source="ocr_debug_bottom_fallback",
            segments=(),
        )

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
    bottom_ratio = max(0.0, min(0.9, 1.0 - (bottom / frame_height)))
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


def _identify_static_texts(
    payload: dict[str, Any],
    frame_width: int,
    frame_height: int,
) -> set[tuple[str, int]]:
    frames = payload.get("frames") or []
    if not frames:
        return set()

    total_frames = len(frames)
    track_occurrences: dict[tuple[str, int], set[int]] = {}
    default_region = _region_from(payload.get("region"))

    for frame_idx, frame in enumerate(frames):
        region = _region_from(frame.get("region")) or default_region
        if not region:
            continue
        for block in frame.get("raw_blocks") or []:
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            norm_text = "".join(c for c in text if c.isalnum() or "\u3400" <= c <= "\u9fff").lower()
            if not norm_text:
                continue
            xs = _box_x_values(block.get("box"))
            ys = _box_y_values(block.get("box"))
            if not xs or not ys:
                continue
            top = region["y"] + min(ys)
            bottom = region["y"] + max(ys)

            y_center = (top + bottom) / 2.0
            y_grid = round(y_center / max(1.0, frame_height * 0.04))

            key = (norm_text, y_grid)
            if key not in track_occurrences:
                track_occurrences[key] = set()
            track_occurrences[key].add(frame_idx)

    static_keys = set()
    for key, frame_indices in track_occurrences.items():
        count = len(frame_indices)
        is_static = False
        if total_frames >= 6:
            if count >= 3 and (count / total_frames) >= 0.28:
                is_static = True
        else:
            if count >= 2:
                is_static = True
        if is_static:
            static_keys.add(key)
    return static_keys


def _collect_frame_text_bounds(
    payload: dict[str, Any],
    *,
    frame_width: int,
    frame_height: int,
) -> list[_FrameTextBounds]:
    static_keys = _identify_static_texts(payload, frame_width=frame_width, frame_height=frame_height)
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
                norm_text = "".join(c for c in parsed.text if c.isalnum() or "\u3400" <= c <= "\u9fff").lower()
                y_center = (parsed.top + parsed.bottom) / 2.0
                y_grid = round(y_center / max(1.0, frame_height * 0.04))

                is_static = False
                for dy in (0, -1, 1):
                    if (norm_text, y_grid + dy) in static_keys:
                        is_static = True
                        break
                if is_static:
                    continue
                blocks.append(parsed)
        if not blocks:
            continue
        selected = _candidate_subtitle_blocks(blocks, frame_width=frame_width, frame_height=frame_height)
        cluster = _best_subtitle_cluster(selected, frame_width=frame_width, frame_height=frame_height)
        if not cluster:
            continue
        timestamp_ms = _safe_int(frame.get("timestamp_ms"), 0)
        confidence = _average([block.confidence for block in cluster if block.confidence > 0])
        frame_bounds.append(
            _FrameTextBounds(
                timestamp_ms=max(0, timestamp_ms),
                text=" ".join(block.text for block in cluster if block.text).strip(),
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
    if bottom < frame_height * 0.05:
        return None
    if block_height / frame_height > 0.18:
        return None
    return _BlockBounds(
        text=text,
        left=max(0.0, left),
        top=max(0.0, top),
        right=min(float(frame_width), right),
        bottom=min(float(frame_height), bottom),
        confidence=confidence,
        has_cjk=has_cjk,
    )


def _candidate_subtitle_blocks(
    blocks: list[_BlockBounds],
    *,
    frame_width: int,
    frame_height: int,
) -> list[_BlockBounds]:
    candidates: list[_BlockBounds] = []
    safe_width = max(1.0, float(frame_width))
    safe_height = max(1.0, float(frame_height))
    for block in blocks:
        width_ratio = (block.right - block.left) / safe_width
        height_ratio = (block.bottom - block.top) / safe_height
        bottom_ratio = block.bottom / safe_height
        center_x_ratio = ((block.left + block.right) / 2.0) / safe_width
        centrality = _center_score(center_x_ratio)
        text_length = _visible_text_length(block.text)
        cjk_length = _cjk_char_count(block.text)

        if bottom_ratio < MIN_MID_SCREEN_SUBTITLE_BOTTOM_RATIO:
            continue

        # Bộ lọc thông minh: Nếu chữ ở phần giữa/trên màn hình (bottom_ratio < 0.72),
        # bắt buộc phải nằm sát trung tâm trục ngang (trục X) và có chiều cao vừa phải (height_ratio <= 0.11).
        # Bộ lọc này giúp loại bỏ chữ in trên bao bì sản phẩm hoặc logo mà vẫn hỗ trợ
        # quét phụ đề thực sự nằm ở giữa/trên màn hình (luôn được căn giữa).
        if bottom_ratio < 0.72:
            if centrality < 0.82:
                continue
            if height_ratio > 0.11:
                continue

        if text_length <= 2 and width_ratio < 0.22:
            continue
        if width_ratio < MIN_SUBTITLE_TEXT_WIDTH_RATIO and centrality < 0.62:
            continue
        if height_ratio > 0.1 and width_ratio < 0.16:
            continue

        subtitle_like = width_ratio >= 0.24 or centrality >= 0.7 or text_length >= 5
        if block.has_cjk and subtitle_like and (
            block.confidence >= MIN_DYNAMIC_CJK_CONFIDENCE
            or cjk_length >= 3
            or (bottom_ratio >= BOTTOM_LANE_BOTTOM_RATIO and width_ratio >= 0.3)
        ):
            candidates.append(block)
            continue
        if block.confidence >= MIN_DYNAMIC_NON_CJK_CONFIDENCE and subtitle_like:
            candidates.append(block)
    if candidates:
        return candidates
    return [
        block
        for block in blocks
        if block.has_cjk
        and block.bottom / safe_height >= BOTTOM_LANE_BOTTOM_RATIO
    ]


def _best_subtitle_cluster(blocks: list[_BlockBounds], *, frame_width: int, frame_height: int) -> list[_BlockBounds]:
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
    return max(clusters, key=lambda cluster: _cluster_score(cluster, frame_width=frame_width, frame_height=frame_height))


def _cluster_score(cluster: list[_BlockBounds], *, frame_width: int, frame_height: int) -> float:
    confidence = _average([block.confidence for block in cluster if block.confidence > 0])
    has_cjk = any(block.has_cjk for block in cluster)
    bottom_ratio = max(block.bottom for block in cluster) / max(1.0, float(frame_height))
    top_ratio = min(block.top for block in cluster) / max(1.0, float(frame_height))
    left = min(block.left for block in cluster)
    right = max(block.right for block in cluster)
    width_ratio = (right - left) / max(1.0, float(frame_width))
    text_height = sum(block.bottom - block.top for block in cluster) / max(1.0, float(frame_height))
    center_x_ratio = ((left + right) / 2.0) / max(1.0, float(frame_width))
    center_y_ratio = ((top_ratio + bottom_ratio) / 2.0)
    text_length = sum(_visible_text_length(block.text) for block in cluster)
    center_bonus = _center_score(center_x_ratio) * 1.8
    lane_bonus = 1.0 if 0.35 <= center_y_ratio <= 0.86 else 0.0
    if bottom_ratio >= BOTTOM_LANE_BOTTOM_RATIO:
        lane_bonus += 0.45
    if bottom_ratio >= 0.92 and width_ratio < 0.45:
        lane_bonus -= 2.0
    if top_ratio < 0.05:
        lane_bonus -= 1.6
    return (
        (0.9 if has_cjk else 0.0)
        + len(cluster) * 0.25
        + confidence * 1.4
        + width_ratio * 3.0
        + min(1.0, text_height * 7.0)
        + min(1.4, text_length / 12.0)
        + center_bonus
        + lane_bonus
    )


def _select_subtitle_lane(
    frame_bounds: list[_FrameTextBounds],
    *,
    frame_width: int,
    frame_height: int,
) -> list[_FrameTextBounds]:
    if len(frame_bounds) <= 1:
        return frame_bounds
    max_gap = max(42.0, frame_height * 0.075)
    lanes: list[list[_FrameTextBounds]] = []
    for item in sorted(frame_bounds, key=lambda bound: (bound.top + bound.bottom) / 2.0):
        center = (item.top + item.bottom) / 2.0
        if not lanes:
            lanes.append([item])
            continue
        current = lanes[-1]
        current_centers = [(bound.top + bound.bottom) / 2.0 for bound in current]
        if center <= max(current_centers) + max_gap:
            current.append(item)
        else:
            lanes.append([item])
    return max(lanes, key=lambda lane: _lane_score(lane, frame_width=frame_width, frame_height=frame_height))


def _lane_score(lane: list[_FrameTextBounds], *, frame_width: int, frame_height: int) -> float:
    confidence = _average([item.confidence for item in lane if item.confidence > 0])
    bottom_ratio = _average([item.bottom / max(1.0, float(frame_height)) for item in lane])
    safe_width = max(1.0, float(frame_width))
    width_ratio = _average([(item.right - item.left) / safe_width for item in lane])
    max_width_ratio = max((item.right - item.left) / safe_width for item in lane)
    center_x_ratio = _average([((item.left + item.right) / 2.0) / safe_width for item in lane])
    centers_y = [(item.top + item.bottom) / 2.0 for item in lane]
    vertical_span_ratio = (max(centers_y) - min(centers_y)) / max(1.0, float(frame_height)) if centers_y else 0.0
    text_length = _average([_visible_text_length(item.text) for item in lane])
    stability_bonus = max(0.0, 1.0 - min(1.0, vertical_span_ratio / MAX_DYNAMIC_VERTICAL_SPAN_RATIO)) * 1.4
    score = (
        len(lane) * 0.55
        + confidence * 1.35
        + min(1.0, width_ratio) * 2.7
        + min(1.0, max_width_ratio) * 0.9
        + _center_score(center_x_ratio) * 1.5
        + min(1.2, text_length / 10.0)
        + stability_bonus
    )
    if bottom_ratio >= BOTTOM_LANE_BOTTOM_RATIO:
        score += 0.55
    elif bottom_ratio < MIN_MID_SCREEN_SUBTITLE_BOTTOM_RATIO:
        score -= 1.0
    if bottom_ratio >= 0.92 and width_ratio < 0.45:
        score -= 2.4
    return score


def _should_use_bottom_fallback(frame_bounds: list[_FrameTextBounds], *, frame_height: int) -> bool:
    confidence = _average([item.confidence for item in frame_bounds if item.confidence > 0])
    if confidence >= DYNAMIC_CONFIDENCE_THRESHOLD:
        return False
    bottom_ratio = max(item.bottom for item in frame_bounds) / max(1.0, float(frame_height))
    if bottom_ratio >= BOTTOM_LANE_BOTTOM_RATIO:
        return True
    return confidence < 0.04 and bottom_ratio >= 0.62


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
    if not _stable_enough_for_timed_segments(frame_bounds, frame_height=frame_height):
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


def _stable_enough_for_timed_segments(frame_bounds: list[_FrameTextBounds], *, frame_height: int) -> bool:
    if len(frame_bounds) <= 1:
        return True
    centers_y = [(item.top + item.bottom) / 2.0 for item in frame_bounds]
    vertical_span_ratio = (max(centers_y) - min(centers_y)) / max(1.0, float(frame_height))
    return vertical_span_ratio <= MAX_DYNAMIC_VERTICAL_SPAN_RATIO


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
    # pad_y tỷ lệ theo chiều cao THỰC của text block:
    #   pad_y = text_height × _COVER_PAD_Y_TEXT_RATIO
    # Clamp vào [frame×0.5%, frame×1.8%] để không quá bé hoặc quá to.
    text_height = max(1.0, bottom - top)
    pad_y_by_text = text_height * _COVER_PAD_Y_TEXT_RATIO
    pad_y = max(
        frame_height * _COVER_PAD_Y_MIN_RATIO,
        min(frame_height * _COVER_PAD_Y_MAX_RATIO, pad_y_by_text),
    )
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
        minimum=frame_width * MIN_COVER_WIDTH_RATIO,
        maximum=frame_width * 0.98,
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


def _cjk_char_count(text: str) -> int:
    return sum(1 for char in text if "\u3400" <= char <= "\u9fff")


def _visible_text_length(text: str) -> int:
    return sum(1 for char in str(text) if char.isalnum() or "\u3400" <= char <= "\u9fff")


def _center_score(center_x_ratio: float) -> float:
    return max(0.0, 1.0 - abs(float(center_x_ratio) - 0.5) * 2.0)
