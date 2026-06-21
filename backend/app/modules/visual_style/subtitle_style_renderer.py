from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.script_writer.script_writer import SubtitleLine
from app.modules.visual_style.style_schema import VisualStylePreset
from app.utils.file_utils import ensure_dir


TERMINAL_SENTENCE_PUNCTUATION = (".", "!", "?", "\u2026", "\u3002", "\uff01", "\uff1f")
TRAILING_SOFT_PUNCTUATION_RE = re.compile(r"[\s,;:\-\u2013\u2014\u3001\uff0c\uff1b\uff1a]+$")
MAX_AUTO_LINE_CHARS = 48


@dataclass(frozen=True)
class _CoverRect:
    start: float
    end: float
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center_x(self) -> int:
        return int(self.left + (self.right - self.left) / 2)

    @property
    def center_y(self) -> int:
        return int(self.top + (self.bottom - self.top) / 2)


def generate_ass_subtitle(
    srt_or_script_subtitles: list[Any],
    preset: VisualStylePreset,
    video_width: int,
    video_height: int,
    output_path: str,
    *,
    cover_background_enabled: bool = False,
    cover_background_color: str = "#000000",
    cover_background_opacity: float = 0.86,
    cover_background_height_ratio: float | None = None,
    cover_background_bottom_ratio: float = 0.0,
    cover_background_segments: list[dict[str, Any]] | None = None,
    cover_background_lead_seconds: float = 0.0,
    cover_background_tail_seconds: float = 0.0,
    cover_background_radius_ratio: float = 0.0,
    cover_background_text_y_offset_ratio: float = 0.0,
    cover_background_reference_lines: list[Any] | None = None,
    cover_background_draw: bool = True,
) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    lines = _normalize_subtitle_lines(srt_or_script_subtitles)
    subtitle = preset.subtitle
    overlay = preset.overlay
    if cover_background_enabled:
        cover_height_ratio = _clamp_float(
            cover_background_height_ratio if cover_background_height_ratio is not None else overlay.height_ratio,
            0.08,
            0.45,
        )
        cover_bottom_ratio = _clamp_float(cover_background_bottom_ratio, 0.0, 0.9)
        cover_bottom = max(1, video_height - int(video_height * cover_bottom_ratio))
        cover_height = max(1, int(video_height * cover_height_ratio))
        cover_top = max(0, cover_bottom - cover_height)
        default_cover_rect = _CoverRect(0.0, float("inf"), 0, cover_top, video_width, cover_bottom)
        cover_segments = _normalize_cover_segments(cover_background_segments, video_width, video_height)
        subtitle_y = default_cover_rect.center_y
        cover_text_y_offset = int(video_height * _clamp_float(cover_background_text_y_offset_ratio, -0.2, 0.2))
    else:
        panel_height = int(video_height * overlay.height_ratio)
        panel_margin_bottom = max(18, min(video_height // 24, overlay.padding_y // 2))
        panel_top = video_height - panel_height - panel_margin_bottom
        subtitle_y = int(panel_top + panel_height / 2)
        default_cover_rect = _CoverRect(0.0, float("inf"), 0, 0, video_width, 0)
        cover_segments = []
        cover_text_y_offset = 0
    margin_l = max(40, overlay.padding_x)
    margin_r = max(40, overlay.padding_x)
    margin_v = max(24, video_height - subtitle_y)
    shadow = int(getattr(subtitle, "shadow_size", 2)) if subtitle.shadow_enabled else 0
    back_alpha = max(0.0, min(1.0, subtitle.shadow_opacity)) if subtitle.shadow_enabled else 0.0

    content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,"
        f"{subtitle.font_family},"
        f"{subtitle.font_size},"
        f"{hex_to_ass_color(subtitle.font_color)},"
        "&H000000FF,"
        f"{hex_to_ass_color(subtitle.stroke_color)},"
        f"{hex_to_ass_color(subtitle.shadow_color, back_alpha)},"
        "1,0,0,0,100,100,0,0,1,"
        f"{subtitle.stroke_width},"
        f"{shadow},"
        f"5,{margin_l},{margin_r},{margin_v},1",
    ]

    draw_cover_background = bool(cover_background_enabled and cover_background_draw)

    if draw_cover_background:
        content.append(
            "Style: SubtitleCover,"
            f"{subtitle.font_family},"
            "20,"
            f"{hex_to_ass_color(cover_background_color, cover_background_opacity)},"
            "&H000000FF,"
            f"{hex_to_ass_color(cover_background_color, cover_background_opacity)},"
            "&H00000000,"
            "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1"
        )

    content.extend(
        [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    display_lines = _expand_lines_for_display(lines, subtitle.max_chars_per_line, subtitle.max_lines)
    if draw_cover_background:
        reference_lines = _normalize_subtitle_lines(cover_background_reference_lines or []) or display_lines
        for line in reference_lines:
            start_seconds = float(line.start_hint or 0.0)
            end_seconds = float(line.end_hint or 0.0)
            cover_start = max(0.0, start_seconds - max(0.0, float(cover_background_lead_seconds)))
            cover_end = max(cover_start + 0.05, end_seconds + max(0.0, float(cover_background_tail_seconds)))
            for rect in _cover_rects_for_line(cover_start, cover_end, cover_segments, default_cover_rect):
                if rect.end <= rect.start:
                    continue
                cover_shape = rf"{{\p1\pos(0,0)}}{_cover_shape_path(rect, cover_background_radius_ratio)}{{\p0}}"
                content.append(
                    "Dialogue: 0,"
                    f"{_format_ass_timestamp(rect.start)},"
                    f"{_format_ass_timestamp(rect.end)},"
                    f"SubtitleCover,,0,0,0,,{cover_shape}"
                )

    for line in display_lines:
        start_seconds = float(line.start_hint or 0.0)
        end_seconds = float(line.end_hint or 0.0)
        start = _format_ass_timestamp(start_seconds)
        end = _format_ass_timestamp(end_seconds)
        display_rect = default_cover_rect
        if cover_background_enabled:
            text_rects = _cover_rects_for_line(start_seconds, end_seconds, cover_segments, default_cover_rect)
            display_rect = max(text_rects, key=lambda item: item.end - item.start) if text_rects else default_cover_rect
        wrapped = r"\N".join(
            _escape_ass_text(part)
            for part in wrap_subtitle_text(line.text, subtitle.max_chars_per_line, subtitle.max_lines)
        )
        subtitle_x = display_rect.center_x if cover_background_enabled else video_width // 2
        if cover_background_enabled:
            display_y = _clamp_int(
                display_rect.center_y + cover_text_y_offset,
                display_rect.top + 4,
                display_rect.bottom - 4,
            )
        else:
            display_y = subtitle_y
        positioned = rf"{{\pos({subtitle_x},{display_y})}}{wrapped}"
        content.append(
            f"Dialogue: {1 if cover_background_enabled else 0},"
            f"{start},"
            f"{end},"
            f"Default,,0,0,0,,{positioned}"
        )

    target.write_text("\n".join(content) + "\n", encoding="utf-8")
    return str(target)


def hex_to_ass_color(hex_color: str, alpha: float = 1.0) -> str:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) != 6:
        raise ValueError(f"ASS color requires #RRGGBB input: {hex_color}")
    red = cleaned[0:2]
    green = cleaned[2:4]
    blue = cleaned[4:6]
    ass_alpha = int(round((1.0 - max(0.0, min(1.0, alpha))) * 255))
    return f"&H{ass_alpha:02X}{blue}{green}{red}"


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    if maximum < minimum:
        return int(value)
    return max(minimum, min(maximum, int(value)))


def _normalize_cover_segments(
    segments: list[dict[str, Any]] | None,
    video_width: int,
    video_height: int,
) -> list[_CoverRect]:
    normalized: list[_CoverRect] = []
    for segment in segments or []:
        if not isinstance(segment, dict):
            continue
        start = _safe_float(segment.get("start"), 0.0)
        end = _safe_float(segment.get("end"), start)
        if end <= start:
            continue
        left_ratio = _clamp_float(_safe_float(segment.get("left_ratio"), 0.0), 0.0, 1.0)
        right_ratio = _clamp_float(_safe_float(segment.get("right_ratio"), 1.0), 0.0, 1.0)
        top_ratio = _clamp_float(_safe_float(segment.get("top_ratio"), 0.0), 0.0, 1.0)
        bottom_ratio = _clamp_float(
            _safe_float(segment.get("bottom_edge_ratio", segment.get("bottom_ratio")), top_ratio),
            0.0,
            1.0,
        )
        if right_ratio <= left_ratio or bottom_ratio <= top_ratio:
            continue
        left = max(0, min(video_width - 1, int(round(video_width * left_ratio))))
        right = max(left + 1, min(video_width, int(round(video_width * right_ratio))))
        top = max(0, min(video_height - 1, int(round(video_height * top_ratio))))
        bottom = max(top + 1, min(video_height, int(round(video_height * bottom_ratio))))
        normalized.append(_CoverRect(start, end, left, top, right, bottom))
    return sorted(normalized, key=lambda item: (item.start, item.end))


def _cover_rects_for_line(
    start: float,
    end: float,
    segments: list[_CoverRect],
    default_rect: _CoverRect,
) -> list[_CoverRect]:
    if end <= start:
        return []
    overlaps: list[_CoverRect] = []
    for segment in segments:
        if segment.end <= start or segment.start >= end:
            continue
        overlap_start = max(start, segment.start)
        overlap_end = min(end, segment.end)
        if overlap_end <= overlap_start:
            continue
        overlaps.append(
            _CoverRect(
                overlap_start,
                overlap_end,
                segment.left,
                segment.top,
                segment.right,
                segment.bottom,
            )
        )
    if overlaps:
        return overlaps
    nearest = _nearest_cover_rect(start + (end - start) / 2.0, segments) or default_rect
    return [_CoverRect(start, end, nearest.left, nearest.top, nearest.right, nearest.bottom)]


def _cover_shape_path(rect: _CoverRect, radius_ratio: float) -> str:
    width = max(1, rect.right - rect.left)
    height = max(1, rect.bottom - rect.top)
    radius = int(round(min(width, height) * _clamp_float(radius_ratio, 0.0, 0.2)))
    if radius <= 1:
        return (
            f"m {rect.left} {rect.top} l {rect.right} {rect.top} "
            f"l {rect.right} {rect.bottom} l {rect.left} {rect.bottom}"
        )

    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    radius = min(radius, width // 2, height // 2)
    kappa = 0.5522847498
    control = max(1, int(round(radius * kappa)))
    return " ".join(
        [
            f"m {left + radius} {top}",
            f"l {right - radius} {top}",
            f"b {right - radius + control} {top} {right} {top + radius - control} {right} {top + radius}",
            f"l {right} {bottom - radius}",
            f"b {right} {bottom - radius + control} {right - radius + control} {bottom} {right - radius} {bottom}",
            f"l {left + radius} {bottom}",
            f"b {left + radius - control} {bottom} {left} {bottom - radius + control} {left} {bottom - radius}",
            f"l {left} {top + radius}",
            f"b {left} {top + radius - control} {left + radius - control} {top} {left + radius} {top}",
        ]
    )


def _nearest_cover_rect(timestamp: float, segments: list[_CoverRect]) -> _CoverRect | None:
    if not segments:
        return None
    return min(
        segments,
        key=lambda segment: 0.0
        if segment.start <= timestamp <= segment.end
        else min(abs(timestamp - segment.start), abs(timestamp - segment.end)),
    )


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def wrap_subtitle_text(text: str, max_chars_per_line: int, max_lines: int) -> list[str]:
    cleaned = _clean_display_text(text)
    if not cleaned:
        return [""]
    lines = _wrap_as_display_lines(cleaned, max_chars_per_line, max_lines)
    if lines:
        return lines
    return _rebalance_short_text_lines(_wrap_lines(cleaned, max_chars_per_line), max_chars_per_line)


def _expand_lines_for_display(
    lines: list[SubtitleLine],
    max_chars_per_line: int,
    max_lines: int,
) -> list[SubtitleLine]:
    expanded: list[SubtitleLine] = []
    for line in lines:
        chunks = _split_text_for_display(line.text, max_chars_per_line, max_lines)
        if not chunks:
            continue
        start = float(line.start_hint or 0.0)
        end = float(line.end_hint or 0.0)
        if len(chunks) == 1:
            expanded.append(line.model_copy(update={"text": chunks[0]}))
            continue

        duration = max(0.1, end - start)
        chunk_duration = duration / len(chunks)
        for index, chunk in enumerate(chunks):
            chunk_start = start + chunk_duration * index
            chunk_end = end if index == len(chunks) - 1 else start + chunk_duration * (index + 1)
            if chunk_end <= chunk_start:
                continue
            expanded.append(
                line.model_copy(
                    update={
                        "start_hint": chunk_start,
                        "end_hint": chunk_end,
                        "text": chunk,
                    }
                )
            )
    return expanded


def _split_text_for_display(text: str, max_chars_per_line: int, max_lines: int) -> list[str]:
    cleaned = _clean_display_text(text)
    if not cleaned:
        return []

    line_limit = max(10, int(max_chars_per_line))
    lines_per_chunk = max(1, int(max_lines))
    chunks: list[str] = []
    for sentence in _split_display_sentences(cleaned):
        chunks.extend(_display_chunks_for_sentence(sentence, line_limit, lines_per_chunk))
    return _rebalance_short_display_chunks(chunks, line_limit)


def _clean_display_text(text: str) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split()).strip()


def _split_display_sentences(text: str) -> list[str]:
    cleaned = _clean_display_text(text)
    if not cleaned:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?\u2026\u3002\uff01\uff1f])\s+", cleaned) if part.strip()]
    return sentences or [cleaned]


def _display_chunks_for_sentence(sentence: str, line_limit: int, lines_per_chunk: int) -> list[str]:
    text = _ensure_sentence_stop(sentence)
    if not text:
        return []
    lines = _wrap_as_display_lines(text, line_limit, lines_per_chunk)
    if lines:
        return ["\n".join(lines)]

    chunks: list[str] = []
    current_words: list[str] = []
    for word in text.split():
        candidate = " ".join([*current_words, word])
        if current_words and _wrap_as_display_lines(candidate, line_limit, lines_per_chunk) is None:
            chunk_lines = _wrap_as_display_lines(" ".join(current_words), line_limit, lines_per_chunk)
            chunks.append("\n".join(chunk_lines or _wrap_lines(" ".join(current_words), MAX_AUTO_LINE_CHARS)))
            current_words = [word]
        else:
            current_words.append(word)
    if current_words:
        chunk_lines = _wrap_as_display_lines(" ".join(current_words), line_limit, lines_per_chunk)
        chunks.append("\n".join(chunk_lines or _wrap_lines(" ".join(current_words), MAX_AUTO_LINE_CHARS)))
    return [chunk for chunk in chunks if chunk.strip()]


def _wrap_as_display_lines(text: str, max_chars_per_line: int, max_lines: int) -> list[str] | None:
    cleaned = _clean_display_text(text)
    if not cleaned:
        return []
    line_limit = max(10, int(max_chars_per_line))
    lines_per_chunk = max(1, int(max_lines))
    needed_limit = min(MAX_AUTO_LINE_CHARS, max(line_limit, (len(cleaned) + lines_per_chunk - 1) // lines_per_chunk))
    for width in dict.fromkeys([line_limit, needed_limit, MAX_AUTO_LINE_CHARS]):
        lines = _wrap_lines(cleaned, width)
        if len(lines) <= lines_per_chunk:
            return _rebalance_short_text_lines(lines, width)
    return None


def _wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(
        text,
        width=max(10, int(width)),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]


def _ensure_sentence_stop(text: str) -> str:
    cleaned = _clean_display_text(text)
    if not cleaned:
        return ""
    if cleaned.rstrip().endswith(TERMINAL_SENTENCE_PUNCTUATION):
        return cleaned
    cleaned = TRAILING_SOFT_PUNCTUATION_RE.sub("", cleaned).rstrip()
    return f"{cleaned}." if cleaned else ""


def _rebalance_short_display_chunks(chunks: list[str], line_limit: int) -> list[str]:
    if len(chunks) < 2:
        return chunks
    previous_words = chunks[-2].replace("\n", " ").split()
    last_words = chunks[-1].replace("\n", " ").split()
    if len(last_words) != 1 or len(last_words[0]) > 8 or len(previous_words) < 2:
        return chunks
    moved_word = previous_words.pop()
    new_last = f"{moved_word} {last_words[0]}"
    if len(new_last) > line_limit + 8:
        return chunks
    previous_lines = textwrap.wrap(
        " ".join(previous_words),
        width=line_limit,
        break_long_words=False,
        break_on_hyphens=False,
    )
    chunks[-2] = "\n".join(_rebalance_short_text_lines(previous_lines, line_limit))
    chunks[-1] = new_last
    return [chunk for chunk in chunks if chunk.strip()]


def _rebalance_short_text_lines(lines: list[str], line_limit: int) -> list[str]:
    if len(lines) < 2:
        return lines
    balanced = list(lines)
    while len(balanced) >= 2:
        last_words = balanced[-1].split()
        previous_words = balanced[-2].split()
        if len(last_words) != 1 or len(last_words[0]) > 8 or len(previous_words) < 2:
            break
        moved_word = previous_words.pop()
        new_last = f"{moved_word} {last_words[0]}"
        if len(new_last) > line_limit + 8:
            break
        balanced[-2] = " ".join(previous_words)
        balanced[-1] = new_last
        if not balanced[-2].strip():
            balanced.pop(-2)
            continue
        break
    return balanced


def _normalize_subtitle_lines(items: list[Any]) -> list[SubtitleLine]:
    lines: list[SubtitleLine] = []
    for item in items:
        if isinstance(item, SubtitleLine):
            line = item
        elif isinstance(item, dict):
            line = SubtitleLine(
                start_hint=item.get("start_hint") if item.get("start_hint") is not None else item.get("start"),
                end_hint=item.get("end_hint") if item.get("end_hint") is not None else item.get("end"),
                text=str(item.get("text") or ""),
            )
        else:
            line = SubtitleLine.model_validate(item)
        if (line.end_hint or 0) > (line.start_hint or 0) and line.text.strip():
            lines.append(line)
    return lines


def _format_ass_timestamp(seconds: float) -> str:
    centiseconds = int(round(max(0.0, seconds) * 100))
    hours = centiseconds // 360_000
    centiseconds %= 360_000
    minutes = centiseconds // 6_000
    centiseconds %= 6_000
    secs = centiseconds // 100
    centis = centiseconds % 100
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape_ass_text(text: str) -> str:
    return str(text).replace("{", r"\{").replace("}", r"\}")
