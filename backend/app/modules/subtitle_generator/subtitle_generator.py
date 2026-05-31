from __future__ import annotations

import re
import textwrap
from pathlib import Path

from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine
from app.modules.script_writer.timing import build_subtitle_timeline
from app.utils.file_utils import ensure_dir


class SubtitleGenerator:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.last_active_duration: float | None = None

    def generate_srt(
        self,
        script: ProductVideoScript,
        target_video_duration: float,
        voice_duration: float | str | None = None,
        output_path: str | None = None,
        subtitle_lines: list[SubtitleLine] | None = None,
    ) -> str:
        if isinstance(voice_duration, str) and output_path is None:
            output_path = voice_duration
            voice_duration = None
        if output_path is None:
            raise ValueError("output_path is required for subtitle generation.")

        target = Path(output_path)
        ensure_dir(target.parent)
        lines = self._normalize_lines(script, target_video_duration, voice_duration, subtitle_lines)

        blocks: list[str] = []
        for index, line in enumerate(lines, start=1):
            text = "\n".join(self._wrap_text(line.text))
            blocks.append(
                "\n".join(
                    [
                        str(index),
                        f"{self._format_timestamp(line.start_hint or 0)} --> {self._format_timestamp(line.end_hint or 0)}",
                        text,
                    ]
                )
            )

        target.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return str(target)

    def generate_ass(
        self,
        script: ProductVideoScript,
        target_video_duration: float,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
        font_size: int = 30,
        overlay_height: int = 33,
        subtitle_lines: list[SubtitleLine] | None = None,
        voice_duration: float | None = None,
    ) -> str:
        target = Path(output_path)
        ensure_dir(target.parent)
        lines = self._normalize_lines(script, target_video_duration, voice_duration, subtitle_lines)
        size = max(24, min(96, font_size))
        overlay_fraction = max(0.10, min(0.45, overlay_height / 100.0))
        overlay_center_y = int(height * (1.0 - overlay_fraction / 2.0))
        wrap_width = max(12, min(24, int(width / (size * 0.62))))

        content = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,"
            f"{size},&H00FFFFFF,&H000000FF,&H00101010,&H96000000,"
            "1,0,0,0,100,100,0,0,1,4,0,5,80,80,0,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for line in lines:
            wrapped_text = r"\N".join(
                self._escape_ass_text(part) for part in self._wrap_text(line.text, width=wrap_width, max_lines=2)
            )
            positioned_text = rf"{{\pos({width // 2},{overlay_center_y})}}{wrapped_text}"
            content.append(
                "Dialogue: 0,"
                f"{self._format_ass_timestamp(line.start_hint or 0)},"
                f"{self._format_ass_timestamp(line.end_hint or 0)},"
                f"Default,,0,0,0,,{positioned_text}"
            )

        target.write_text("\n".join(content) + "\n", encoding="utf-8")
        return str(target)

    def _normalize_lines(
        self,
        script: ProductVideoScript,
        target_video_duration: float,
        voice_duration: float | str | None = None,
        subtitle_lines: list[SubtitleLine] | None = None,
    ) -> list[SubtitleLine]:
        active_duration = self._active_duration(target_video_duration, voice_duration if not isinstance(voice_duration, str) else None)
        lines = subtitle_lines or build_subtitle_timeline(script, active_duration)
        return self._prevent_overlaps(
            [
                SubtitleLine(
                    start_hint=max(0.0, min(float(line.start_hint or 0.0), active_duration)),
                    end_hint=max(0.0, min(float(line.end_hint or 0.0), active_duration)),
                    text=self._sanitize_text(line.text),
                )
                for line in lines
            ]
        )

    def _active_duration(self, target_video_duration: float, voice_duration: float | None = None) -> float:
        self.warnings = []
        target_video_duration = max(0.1, float(target_video_duration))
        hard_cap = max(0.1, target_video_duration - 0.1)
        active_duration = hard_cap
        if voice_duration is not None and voice_duration > 0:
            if target_video_duration - voice_duration > 2.0:
                self.warnings.append("voice_shorter_than_video")
            if voice_duration - target_video_duration > 1.0:
                self.warnings.append("voice_longer_than_video")
            active_duration = min(hard_cap, float(voice_duration))
        self.last_active_duration = round(active_duration, 3)
        return self.last_active_duration

    @staticmethod
    def _contains_cta_at_end(lines: list[SubtitleLine], cta: str, target_duration: float) -> bool:
        normalized_cta = re.sub(r"\s+", " ", cta.casefold()).strip()
        end_window_start = max(0.0, target_duration - 2.0)
        return any(
            normalized_cta
            and normalized_cta in re.sub(r"\s+", " ", line.text.casefold())
            and (line.end_hint is None or float(line.end_hint) >= end_window_start)
            for line in lines
        )

    @staticmethod
    def _sanitize_text(text: str) -> str:
        cleaned = text.replace("\r", " ").replace("\n", " ")
        cleaned = "".join(char for char in cleaned if char == "\t" or char >= " ")
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _wrap_text(text: str, width: int = 24, max_lines: int | None = 2) -> list[str]:
        wrapped = textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if max_lines is None:
            return wrapped or [text]
        if len(wrapped) <= max_lines:
            return wrapped or [text]

        kept = wrapped[: max_lines - 1]
        last = " ".join(wrapped[max_lines - 1 :])
        if len(last) > width:
            last = textwrap.shorten(last, width=width, placeholder="")
        kept.append(last.strip())
        return kept

    @staticmethod
    def _prevent_overlaps(lines: list[SubtitleLine]) -> list[SubtitleLine]:
        sorted_lines = sorted(lines, key=lambda item: item.start_hint or 0.0)
        for index, line in enumerate(sorted_lines[:-1]):
            next_start = sorted_lines[index + 1].start_hint or 0.0
            current_start = line.start_hint or 0.0
            current_end = line.end_hint or 0.0
            if current_end > next_start:
                line.end_hint = next_start if next_start > current_start else current_start

        return [
            line
            for line in sorted_lines
            if (line.start_hint or 0.0) < (line.end_hint or 0.0)
        ]

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        milliseconds = int(round(seconds * 1000))
        hours = milliseconds // 3_600_000
        milliseconds %= 3_600_000
        minutes = milliseconds // 60_000
        milliseconds %= 60_000
        secs = milliseconds // 1000
        millis = milliseconds % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _format_ass_timestamp(seconds: float) -> str:
        centiseconds = int(round(seconds * 100))
        hours = centiseconds // 360_000
        centiseconds %= 360_000
        minutes = centiseconds // 6_000
        centiseconds %= 6_000
        secs = centiseconds // 100
        centis = centiseconds % 100
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    @staticmethod
    def _escape_ass_text(text: str) -> str:
        return text.replace("{", r"\{").replace("}", r"\}")
