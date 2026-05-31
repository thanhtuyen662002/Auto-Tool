from __future__ import annotations

import re

from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine, VoiceoverLine


def build_voiceover_timeline(script: ProductVideoScript, target_duration: float) -> list[SubtitleLine]:
    voiceover_lines = _voiceover_lines_with_cta(script)
    if not voiceover_lines:
        return []

    parsed_lines = _timeline_from_time_hints(voiceover_lines, target_duration)
    if parsed_lines:
        return parsed_lines

    return _timeline_by_text_weight(voiceover_lines, target_duration)


def build_subtitle_timeline(
    script: ProductVideoScript,
    target_duration: float,
) -> list[SubtitleLine]:
    voice_timeline = build_voiceover_timeline(script, target_duration)
    subtitle_lines: list[SubtitleLine] = []

    for line in voice_timeline:
        start = float(line.start_hint or 0.0)
        end = float(line.end_hint or start)
        duration = max(0.0, end - start)
        sentences = _split_sentences(line.text)
        if not sentences or duration <= 0:
            continue

        weights = [max(1, len(sentence)) for sentence in sentences]
        total_weight = sum(weights)
        cursor = start
        for index, sentence in enumerate(sentences):
            if index == len(sentences) - 1:
                sentence_end = end
            else:
                sentence_duration = duration * (weights[index] / total_weight)
                sentence_end = min(end, cursor + sentence_duration)

            if sentence_end > cursor:
                subtitle_lines.append(
                    SubtitleLine(
                        start_hint=round(cursor, 3),
                        end_hint=round(sentence_end, 3),
                        text=sentence,
                    )
                )
            cursor = sentence_end

    return subtitle_lines


def _voiceover_lines_with_cta(script: ProductVideoScript) -> list[VoiceoverLine]:
    lines = [line for line in script.voiceover if line.text.strip()]
    combined_text = " ".join(line.text for line in lines).casefold()
    cta = script.cta.strip()
    if cta and cta.casefold() not in combined_text:
        lines.append(VoiceoverLine(time_hint="", text=cta))
    return lines


def _timeline_from_time_hints(lines: list[VoiceoverLine], target_duration: float) -> list[SubtitleLine]:
    parsed: list[SubtitleLine] = []
    previous_end = 0.0

    for line in lines:
        hint = _parse_time_hint(line.time_hint)
        if not hint:
            return []

        start, end = hint
        start = max(0.0, min(start, target_duration))
        end = max(0.0, min(end, target_duration))
        if start < previous_end:
            start = previous_end
        if end <= start:
            return []

        parsed.append(
            SubtitleLine(
                start_hint=round(start, 3),
                end_hint=round(end, 3),
                text=line.text.strip(),
            )
        )
        previous_end = end

    if previous_end < target_duration * 0.85:
        return []

    return parsed


def _timeline_by_text_weight(lines: list[VoiceoverLine], target_duration: float) -> list[SubtitleLine]:
    weights = [max(1, len(line.text.strip())) for line in lines]
    total_weight = sum(weights)
    cursor = 0.0
    timeline: list[SubtitleLine] = []

    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            end = target_duration
        else:
            duration = target_duration * (weights[index] / total_weight)
            end = min(target_duration, cursor + duration)

        if end > cursor:
            timeline.append(
                SubtitleLine(
                    start_hint=round(cursor, 3),
                    end_hint=round(end, 3),
                    text=line.text.strip(),
                )
            )
        cursor = end

    return timeline


def _parse_time_hint(value: str) -> tuple[float, float] | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s?", value or "", re.IGNORECASE)
    if not match:
        return None

    start = float(match.group(1))
    end = float(match.group(2))
    if end <= start:
        return None
    return start, end


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?…])\s+", cleaned)
        if part.strip()
    ]
    return sentences or [cleaned]
