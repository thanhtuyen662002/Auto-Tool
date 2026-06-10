from __future__ import annotations

import re
from pathlib import Path

from app.modules.final_output_qa.final_output_qa_schema import PlatformTarget, SubtitleVisibilityInfo


PLAY_RES_Y_RE = re.compile(r"^PlayResY:\s*(\d+)", re.MULTILINE | re.IGNORECASE)
STYLE_RE = re.compile(r"^Style:\s*[^,]*,[^,]*,(\d+(?:\.\d+)?)(?:,[^,]*){18},(\d+),", re.MULTILINE)


class SubtitleVisibilityChecker:
    def check_subtitle_visibility(
        self,
        output_video_path: str,
        ass_path: str | None,
        overlay_path: str | None,
        platform_target: PlatformTarget,
        *,
        subtitle_expected: bool = True,
        overlay_expected: bool = False,
    ) -> SubtitleVisibilityInfo:
        del output_video_path, platform_target
        warnings: list[str] = []
        subtitle_path = Path(ass_path).expanduser().resolve() if ass_path else None
        overlay = Path(overlay_path).expanduser().resolve() if overlay_path else None
        if subtitle_expected and (subtitle_path is None or not subtitle_path.exists()):
            warnings.append("Expected subtitle file is missing; burn-in cannot be verified from artifacts.")
        if overlay_expected and (overlay is None or not overlay.exists()):
            warnings.append("Visual style expects an overlay but the overlay artifact is missing.")

        zone: dict | None = None
        safe_zone_ok = True
        if subtitle_path and subtitle_path.exists() and subtitle_path.suffix.lower() == ".ass":
            try:
                content = subtitle_path.read_text(encoding="utf-8-sig", errors="replace")
                play_res_y = int(PLAY_RES_Y_RE.search(content).group(1)) if PLAY_RES_Y_RE.search(content) else 1920
                style = STYLE_RE.search(content)
                font_size = float(style.group(1)) if style else None
                margin_v = int(style.group(2)) if style else None
                if margin_v is not None:
                    baseline_ratio = round(1 - margin_v / max(play_res_y, 1), 4)
                    zone = {
                        "play_res_y": play_res_y,
                        "margin_v": margin_v,
                        "baseline_ratio": baseline_ratio,
                        "font_size": font_size,
                    }
                    if baseline_ratio > 0.94 or margin_v < max(40, int(play_res_y * 0.035)):
                        safe_zone_ok = False
                        warnings.append("Subtitle zone is too close to the bottom edge for platform UI safety.")
                if font_size is not None and font_size > play_res_y * 0.065:
                    safe_zone_ok = False
                    warnings.append("Subtitle font size is unusually large for the output height.")
            except OSError as exc:
                warnings.append(f"Could not inspect ASS subtitle style: {exc}")

        return SubtitleVisibilityInfo(
            subtitle_expected=subtitle_expected,
            subtitle_file_path=str(subtitle_path) if subtitle_path else None,
            overlay_file_path=str(overlay) if overlay else None,
            estimated_subtitle_zone=zone,
            safe_zone_ok=safe_zone_ok,
            warnings=warnings,
        )
