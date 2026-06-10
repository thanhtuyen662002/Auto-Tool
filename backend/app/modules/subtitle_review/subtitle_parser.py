from __future__ import annotations

import re
from pathlib import Path

from app.modules.subtitle_review.subtitle_review_schema import SubtitleLine
from app.utils.file_utils import ensure_dir

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


def parse_srt_to_lines(translated_srt_path: str, source_srt_path: str | None = None) -> list[SubtitleLine]:
    translated_blocks = _parse_srt_blocks(translated_srt_path)
    source_by_index = _source_map(source_srt_path)
    source_count = len(source_by_index)
    lines: list[SubtitleLine] = []

    for fallback_index, block in enumerate(translated_blocks, start=1):
        source_text = source_by_index.get(block["index"]) or source_by_index.get(fallback_index)
        warnings: list[str] = []
        if source_srt_path and source_count and not source_text:
            warnings.append("Không map được source subtitle theo index.")
        lines.append(
            SubtitleLine(
                index=int(block["index"]),
                start_ms=int(block["start_ms"]),
                end_ms=int(block["end_ms"]),
                source_text=source_text,
                translated_text=str(block["text"]),
                warnings=warnings,
            )
        )

    if source_srt_path and source_count and source_count != len(translated_blocks):
        for index, line in enumerate(lines):
            lines[index] = line.model_copy(
                update={"warnings": [*line.warnings, "Số block source và translated SRT lệch nhau."]}
            )
    return lines


def write_lines_to_srt(lines: list[SubtitleLine], output_path: str, use_edited_text: bool = True) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    parts: list[str] = []
    sorted_lines = sorted(lines, key=lambda line: (line.start_ms, line.index))
    for output_index, line in enumerate(sorted_lines, start=1):
        text = line.edited_text if use_edited_text and line.edited_text else line.translated_text
        parts.append(
            "\n".join(
                [
                    str(output_index),
                    f"{ms_to_srt_timestamp(line.start_ms)} --> {ms_to_srt_timestamp(line.end_ms)}",
                    (text or "").strip(),
                ]
            )
        )
    target.write_text("\n\n".join(parts) + ("\n" if parts else ""), encoding="utf-8")
    return str(target)


def ms_to_srt_timestamp(ms: int) -> str:
    value = max(0, int(ms))
    hours = value // 3_600_000
    value %= 3_600_000
    minutes = value // 60_000
    value %= 60_000
    seconds = value // 1000
    millis = value % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def srt_timestamp_to_ms(value: str) -> int:
    head, millis = value.strip().replace(".", ",").split(",", 1)
    hours, minutes, seconds = [int(part) for part in head.split(":")]
    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + int((millis + "000")[:3])


def _source_map(source_srt_path: str | None) -> dict[int, str]:
    if not source_srt_path:
        return {}
    return {int(block["index"]): str(block["text"]) for block in _parse_srt_blocks(source_srt_path)}


def _parse_srt_blocks(path: str) -> list[dict[str, int | str]]:
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    chunks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    blocks: list[dict[str, int | str]] = []
    fallback_index = 1

    for chunk in chunks:
        lines = [line.strip("\ufeff") for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue
        time_line_index = next((idx for idx, line in enumerate(lines) if "-->" in line), None)
        if time_line_index is None:
            continue
        match = TIMESTAMP_RE.search(lines[time_line_index])
        if not match:
            continue
        index = int(lines[0]) if time_line_index > 0 and lines[0].isdigit() else fallback_index
        blocks.append(
            {
                "index": index,
                "start_ms": srt_timestamp_to_ms(match.group("start")),
                "end_ms": srt_timestamp_to_ms(match.group("end")),
                "text": "\n".join(lines[time_line_index + 1 :]).strip(),
            }
        )
        fallback_index += 1
    return blocks
