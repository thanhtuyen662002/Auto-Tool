from __future__ import annotations

from pathlib import Path

from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRSubtitleLine
from app.modules.subtitle_review.subtitle_parser import ms_to_srt_timestamp
from app.utils.file_utils import ensure_dir


class OCRSRTBuilder:
    def __init__(self, min_duration_ms: int = 500) -> None:
        self.min_duration_ms = max(1, int(min_duration_ms))

    def build_srt(
        self,
        lines: list[OCRSubtitleLine],
        output_srt_path: str,
        video_duration_ms: int,
    ) -> str:
        duration = max(1, int(video_duration_ms))
        sorted_lines = sorted([line for line in lines if line.text.strip()], key=lambda line: (line.start_ms, line.end_ms))
        parts: list[str] = []
        for output_index, line in enumerate(sorted_lines, start=1):
            next_start = sorted_lines[output_index].start_ms if output_index < len(sorted_lines) else None
            start_ms = min(max(0, int(line.start_ms)), duration - 1)
            end_ms = min(max(int(line.end_ms), start_ms + self.min_duration_ms), duration)
            if next_start is not None and next_start > start_ms:
                end_ms = min(end_ms, max(start_ms + 1, next_start - 1))
            if end_ms <= start_ms:
                end_ms = min(duration, start_ms + self.min_duration_ms)
            if end_ms <= start_ms:
                continue
            parts.append(
                "\n".join(
                    [
                        str(output_index),
                        f"{ms_to_srt_timestamp(start_ms)} --> {ms_to_srt_timestamp(end_ms)}",
                        line.text.strip(),
                    ]
                )
            )

        target = Path(output_srt_path)
        ensure_dir(target.parent)
        target.write_text("\n\n".join(parts) + ("\n" if parts else ""), encoding="utf-8")
        return str(target)
