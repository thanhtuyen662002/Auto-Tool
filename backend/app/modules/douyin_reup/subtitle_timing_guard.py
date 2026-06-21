from __future__ import annotations

import re
import textwrap
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.utils.file_utils import ensure_dir

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)
TERMINAL_SENTENCE_PUNCTUATION = (".", "!", "?", "\u2026", "\u3002", "\uff01", "\uff1f")
TRAILING_SOFT_PUNCTUATION_RE = re.compile(r"[\s,;:\-\u2013\u2014\u3001\uff0c\uff1b\uff1a]+$")
MAX_AUTO_LINE_CHARS = 48


@dataclass(frozen=True)
class SubtitleBlock:
    index: int
    start: float
    end: float
    text: str


class SubtitleTimingGuard:
    def guard_timing(
        self,
        source_srt_path: str,
        target_duration: float,
        output_path: str,
        max_chars_per_line: int = 22,
        max_lines: int = 2,
        time_offset_seconds: float = 0.0,
    ) -> str:
        blocks = parse_srt_blocks(source_srt_path)
        fixed: list[SubtitleBlock] = []
        duration = max(0.1, float(target_duration))

        for block in blocks:
            shifted_start = block.start + time_offset_seconds
            shifted_end = block.end + time_offset_seconds
            if shifted_end <= 0:
                continue
            start = min(max(0.0, shifted_start), duration)
            end = min(max(start + 0.25, shifted_end), duration)
            if start >= duration:
                continue
            text = ensure_sentence_punctuation(block.text)
            if not text:
                continue
            for chunk_start, chunk_end, chunk_text in split_block_for_display(
                start=start,
                end=end,
                text=text,
                max_chars_per_line=max_chars_per_line,
                max_lines=max_lines,
            ):
                fixed.append(
                    SubtitleBlock(
                        index=len(fixed) + 1,
                        start=chunk_start,
                        end=chunk_end,
                        text=chunk_text,
                    )
                )

        return write_srt_blocks(fixed, output_path)


def parse_srt_blocks(path: str) -> list[SubtitleBlock]:
    source = Path(path)
    text = source.read_text(encoding="utf-8-sig", errors="replace")
    chunks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    blocks: list[SubtitleBlock] = []
    fallback_index = 1

    for chunk in chunks:
        lines = [line.strip("\ufeff") for line in chunk.split("\n") if line.strip()]
        if not lines:
            continue

        time_line_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if time_line_index is None:
            continue
        match = TIMESTAMP_RE.search(lines[time_line_index])
        if not match:
            continue

        subtitle_text = "\n".join(lines[time_line_index + 1 :]).strip()
        if not subtitle_text:
            continue
        try:
            index_value = int(lines[0]) if time_line_index > 0 and lines[0].isdigit() else fallback_index
        except ValueError:
            index_value = fallback_index
        blocks.append(
            SubtitleBlock(
                index=index_value,
                start=parse_srt_timestamp(match.group("start")),
                end=parse_srt_timestamp(match.group("end")),
                text=subtitle_text,
            )
        )
        fallback_index += 1

    return blocks


def write_srt_blocks(blocks: list[SubtitleBlock], output_path: str) -> str:
    target = Path(output_path)
    ensure_dir(target.parent)
    parts: list[str] = []
    for index, block in enumerate(blocks, start=1):
        parts.append(
            "\n".join(
                [
                    str(index),
                    f"{format_srt_timestamp(block.start)} --> {format_srt_timestamp(block.end)}",
                    block.text.strip(),
                ]
            )
        )
    payload = "\n\n".join(parts) + ("\n" if parts else "")
    _atomic_write_text_with_retry(target, payload)
    return str(target)


def _atomic_write_text_with_retry(target: Path, payload: str, attempts: int = 5) -> None:
    ensure_dir(target.parent)
    last_error: OSError | None = None
    for attempt in range(1, max(1, attempts) + 1):
        temp_path = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(target)
            return
        except OSError as exc:
            last_error = exc
            temp_path.unlink(missing_ok=True)
            if attempt >= attempts:
                break
            time.sleep(0.12 * attempt)
    raise PermissionError(
        f"Không thể ghi file subtitle sau {attempts} lần thử: {target}. "
        "File hoặc thư mục có thể đang bị khóa bởi Windows, antivirus hoặc ứng dụng xem video."
    ) from last_error


def parse_srt_timestamp(value: str) -> float:
    head, millis = value.replace(".", ",").split(",", 1)
    hours, minutes, seconds = [int(part) for part in head.split(":")]
    millis_value = int((millis + "000")[:3])
    return hours * 3600 + minutes * 60 + seconds + millis_value / 1000


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours = milliseconds // 3_600_000
    milliseconds %= 3_600_000
    minutes = milliseconds // 60_000
    milliseconds %= 60_000
    secs = milliseconds // 1000
    millis = milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def clean_subtitle_text(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)
    return " ".join(cleaned.replace("\n", " ").split())


def ensure_sentence_punctuation(text: str) -> str:
    cleaned = clean_subtitle_text(text)
    if not cleaned:
        return ""
    if cleaned.rstrip().endswith(TERMINAL_SENTENCE_PUNCTUATION):
        return cleaned
    cleaned = TRAILING_SOFT_PUNCTUATION_RE.sub("", cleaned).rstrip()
    return f"{cleaned}." if cleaned else ""


def wrap_srt_text(text: str, max_chars_per_line: int = 22, max_lines: int = 2) -> list[str]:
    cleaned = clean_subtitle_text(text)
    if not cleaned:
        return [""]
    return textwrap.wrap(
        cleaned,
        width=max(10, max_chars_per_line),
        break_long_words=False,
        break_on_hyphens=False,
    )


def split_block_for_display(
    start: float,
    end: float,
    text: str,
    max_chars_per_line: int = 22,
    max_lines: int = 2,
) -> list[tuple[float, float, str]]:
    chunks = split_text_for_display(text, max_chars_per_line=max_chars_per_line, max_lines=max_lines)
    if not chunks:
        return []
    if len(chunks) == 1:
        return [(start, end, chunks[0])]

    block_duration = max(0.1, end - start)
    chunk_duration = block_duration / len(chunks)
    result: list[tuple[float, float, str]] = []
    for index, chunk in enumerate(chunks):
        chunk_start = start + chunk_duration * index
        chunk_end = end if index == len(chunks) - 1 else start + chunk_duration * (index + 1)
        if chunk_end <= chunk_start:
            continue
        result.append((chunk_start, chunk_end, chunk))
    return result


def split_text_for_display(text: str, max_chars_per_line: int = 22, max_lines: int = 2) -> list[str]:
    cleaned = clean_subtitle_text(text)
    if not cleaned:
        return []

    line_limit = max(10, int(max_chars_per_line))
    lines_per_chunk = max(1, int(max_lines))
    chunks: list[str] = []
    for sentence in _split_sentences(cleaned):
        sentence_chunks = _display_chunks_for_sentence(sentence, line_limit, lines_per_chunk)
        chunks.extend(sentence_chunks)
    return chunks


def _split_sentences(text: str) -> list[str]:
    cleaned = clean_subtitle_text(text)
    if not cleaned:
        return []
    sentences = [part.strip() for part in re.split(r"(?<=[.!?\u2026\u3002\uff01\uff1f])\s+", cleaned) if part.strip()]
    return sentences or [cleaned]


def _display_chunks_for_sentence(sentence: str, line_limit: int, lines_per_chunk: int) -> list[str]:
    text = ensure_sentence_punctuation(sentence)
    if not text:
        return []
    fitted = _wrap_as_display_chunk(text, line_limit, lines_per_chunk)
    if fitted:
        return [fitted]

    chunks: list[str] = []
    current_words: list[str] = []
    for word in text.split():
        candidate = " ".join([*current_words, word])
        if current_words and _wrap_as_display_chunk(candidate, line_limit, lines_per_chunk) is None:
            chunk = _wrap_as_display_chunk(" ".join(current_words), line_limit, lines_per_chunk)
            chunks.append(chunk or "\n".join(_wrap_lines(" ".join(current_words), MAX_AUTO_LINE_CHARS)))
            current_words = [word]
        else:
            current_words.append(word)
    if current_words:
        chunk = _wrap_as_display_chunk(" ".join(current_words), line_limit, lines_per_chunk)
        chunks.append(chunk or "\n".join(_wrap_lines(" ".join(current_words), MAX_AUTO_LINE_CHARS)))
    return [chunk for chunk in chunks if chunk.strip()]


def _wrap_as_display_chunk(text: str, line_limit: int, lines_per_chunk: int) -> str | None:
    cleaned = clean_subtitle_text(text)
    if not cleaned:
        return None
    needed_limit = min(MAX_AUTO_LINE_CHARS, max(line_limit, (len(cleaned) + lines_per_chunk - 1) // lines_per_chunk))
    for width in dict.fromkeys([line_limit, needed_limit, MAX_AUTO_LINE_CHARS]):
        lines = _wrap_lines(cleaned, width)
        if len(lines) <= lines_per_chunk:
            return "\n".join(lines)
    return None


def _wrap_lines(text: str, width: int) -> list[str]:
    return textwrap.wrap(
        text,
        width=max(10, width),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]
