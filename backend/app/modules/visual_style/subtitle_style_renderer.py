from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from app.modules.script_writer.script_writer import SubtitleLine
from app.modules.visual_style.style_schema import VisualStylePreset
from app.utils.file_utils import ensure_dir


def generate_ass_subtitle(
    srt_or_script_subtitles: list[Any],
    preset: VisualStylePreset,
    video_width: int,
    video_height: int,
    output_path: str,
) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    lines = _normalize_subtitle_lines(srt_or_script_subtitles)
    subtitle = preset.subtitle
    overlay = preset.overlay
    panel_height = int(video_height * overlay.height_ratio)
    panel_margin_bottom = max(18, min(video_height // 24, overlay.padding_y // 2))
    panel_top = video_height - panel_height - panel_margin_bottom
    subtitle_y = int(panel_top + panel_height / 2)
    margin_l = max(40, overlay.padding_x)
    margin_r = max(40, overlay.padding_x)
    margin_v = max(24, video_height - subtitle_y)
    shadow = 2 if subtitle.shadow_enabled else 0
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
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for line in lines:
        wrapped = r"\N".join(
            _escape_ass_text(part)
            for part in wrap_subtitle_text(line.text, subtitle.max_chars_per_line, subtitle.max_lines)
        )
        positioned = rf"{{\pos({video_width // 2},{subtitle_y})}}{wrapped}"
        content.append(
            "Dialogue: 0,"
            f"{_format_ass_timestamp(float(line.start_hint or 0.0))},"
            f"{_format_ass_timestamp(float(line.end_hint or 0.0))},"
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


def wrap_subtitle_text(text: str, max_chars_per_line: int, max_lines: int) -> list[str]:
    cleaned = " ".join(str(text).replace("\r", " ").replace("\n", " ").split())
    if not cleaned:
        return [""]
    wrapped = textwrap.wrap(
        cleaned,
        width=max_chars_per_line,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if len(wrapped) <= max_lines:
        return wrapped
    kept = wrapped[: max(1, max_lines - 1)]
    last = " ".join(wrapped[max(1, max_lines - 1) :])
    if len(last) > max_chars_per_line:
        last = textwrap.shorten(last, width=max_chars_per_line, placeholder="")
    return [*kept, last.strip()][:max_lines]


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
