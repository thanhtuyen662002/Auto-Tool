from __future__ import annotations

from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine, VoiceoverLine
from app.modules.tts.text_cleanup import clean_text_for_tts, estimate_voice_duration


def prepare_script_for_tts(
    script: ProductVideoScript,
    target_duration: float | None,
    language: str = "vi",
    allow_shortening: bool = True,
) -> tuple[ProductVideoScript, list[str]]:
    warnings: list[str] = []
    cleaned_voiceover = [
        VoiceoverLine(time_hint=line.time_hint, text=clean_text_for_tts(line.text))
        for line in script.voiceover
        if clean_text_for_tts(line.text)
    ]
    if not cleaned_voiceover:
        cleaned_voiceover = [VoiceoverLine(time_hint="", text=clean_text_for_tts(script.cta) or script.cta)]

    cleaned_script = script.model_copy(
        update={
            "hook": clean_text_for_tts(script.hook) or script.hook,
            "voiceover": cleaned_voiceover,
            "subtitles": [
                SubtitleLine(
                    start_hint=line.start_hint,
                    end_hint=line.end_hint,
                    text=clean_text_for_tts(line.text),
                )
                for line in script.subtitles
                if clean_text_for_tts(line.text)
            ]
            or [SubtitleLine(start_hint=None, end_hint=None, text=line.text) for line in cleaned_voiceover],
            "cta": clean_text_for_tts(script.cta) or script.cta,
        }
    )

    if not target_duration or target_duration <= 0 or not allow_shortening:
        return cleaned_script, warnings

    full_text = _voiceover_text(cleaned_script)
    estimated = estimate_voice_duration(full_text, language)
    if estimated <= target_duration + 2.0:
        return cleaned_script, warnings

    shortened = _shorten_voiceover(cleaned_script.voiceover, cleaned_script.cta, target_duration, language)
    shortened_script = cleaned_script.model_copy(
        update={
            "voiceover": shortened,
            "subtitles": [
                SubtitleLine(start_hint=None, end_hint=None, text=line.text)
                for line in shortened
            ],
        }
    )
    warnings.append(
        "script_shortened_for_tts: Thời lượng giọng đọc ước tính "
        f"{estimated:.2f}s vượt quá mục tiêu {target_duration:.2f}s nên nội dung đã được rút gọn."
    )
    return shortened_script, warnings


def _shorten_voiceover(
    lines: list[VoiceoverLine],
    cta: str,
    target_duration: float,
    language: str,
) -> list[VoiceoverLine]:
    unique_lines = _dedupe_lines(lines)
    if not unique_lines:
        return [VoiceoverLine(time_hint="", text=cta)]

    cta_clean = clean_text_for_tts(cta)
    selected: list[VoiceoverLine] = [unique_lines[0]]

    middle = unique_lines[1:]
    middle = sorted(middle, key=lambda line: len(line.text))
    for line in middle:
        if cta_clean and cta_clean.casefold() in line.text.casefold():
            continue
        if line.text in {item.text for item in selected}:
            continue
        selected.append(line)
        if len(selected) >= 3:
            break

    if cta_clean and cta_clean.casefold() not in " ".join(line.text for line in selected).casefold():
        selected.append(VoiceoverLine(time_hint="", text=cta_clean))

    while len(selected) > 2 and estimate_voice_duration(_lines_text(selected), language) > target_duration + 2.0:
        removable = selected[1:-1] if len(selected) > 2 else selected
        longest = max(removable, key=lambda line: len(line.text))
        selected.remove(longest)

    return [VoiceoverLine(time_hint="", text=line.text) for line in selected if line.text.strip()]


def _dedupe_lines(lines: list[VoiceoverLine]) -> list[VoiceoverLine]:
    seen: set[str] = set()
    deduped: list[VoiceoverLine] = []
    for line in lines:
        key = line.text.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _voiceover_text(script: ProductVideoScript) -> str:
    return _lines_text(script.voiceover)


def _lines_text(lines: list[VoiceoverLine]) -> str:
    return " ".join(line.text for line in lines if line.text.strip())
