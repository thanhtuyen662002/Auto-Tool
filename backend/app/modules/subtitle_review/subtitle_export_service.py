from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.subtitle_review.subtitle_parser import write_lines_to_srt
from app.modules.subtitle_review.subtitle_review_schema import SubtitleReviewDocument
from app.modules.visual_style.style_schema import VisualStyleSettings
from app.modules.visual_style.subtitle_style_renderer import generate_ass_subtitle
from app.modules.visual_style.visual_style_service import VisualStyleService, parse_resolution
from app.utils.file_utils import ensure_dir


class SubtitleExportService:
    def export_corrected_srt(self, document: SubtitleReviewDocument) -> str:
        output_path = _corrected_srt_path(document)
        return write_lines_to_srt(document.lines, str(output_path), use_edited_text=True)

    def export_corrected_ass(
        self,
        document: SubtitleReviewDocument,
        visual_style_preset_id: str | None = None,
        resolution: str = "1080x1920",
    ) -> str:
        width, height = _video_size(document.video_path, fallback_resolution=resolution)
        preset = VisualStyleService().resolve_preset(
            VisualStyleSettings(preset_id=visual_style_preset_id or "clean_review_light")
        )
        output_path = _corrected_ass_path(document)
        subtitle_lines = [
            {
                "start_hint": line.start_ms / 1000,
                "end_hint": line.end_ms / 1000,
                "text": line.edited_text or line.translated_text,
            }
            for line in document.lines
        ]
        return generate_ass_subtitle(subtitle_lines, preset, width, height, str(output_path))


def _corrected_srt_path(document: SubtitleReviewDocument) -> Path:
    base = Path(document.translated_srt_path)
    stem = base.stem.replace("_fixed", "")
    return ensure_dir(base.parent) / f"{stem}.corrected.srt"


def _corrected_ass_path(document: SubtitleReviewDocument) -> Path:
    base = Path(document.translated_srt_path)
    stem = base.stem.replace("_fixed", "")
    return ensure_dir(base.parent) / f"{stem}.corrected.ass"


def _video_size(video_path: str, fallback_resolution: str) -> tuple[int, int]:
    try:
        media = probe_video(video_path)
        if media.width > 0 and media.height > 0:
            return media.width, media.height
    except Exception:
        pass
    return parse_resolution(fallback_resolution)
