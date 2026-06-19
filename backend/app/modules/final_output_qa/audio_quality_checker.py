from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.modules.final_output_qa.final_output_qa_schema import AudioQualityInfo
from app.utils.dependency_manager import DependencyError, resolve_tool
from app.utils.subprocess_utils import run_hidden


VOLUME_RE = re.compile(r"(mean_volume|max_volume):\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", re.IGNORECASE)


class AudioQualityChecker:
    def analyze_audio(self, video_path: str, *, has_audio: bool | None = None) -> AudioQualityInfo:
        path = Path(video_path).expanduser().resolve()
        if has_audio is False:
            return AudioQualityInfo(has_audio=False)
        if not path.exists():
            return AudioQualityInfo(has_audio=False, warnings=["Audio analysis skipped because video file is missing."])
        try:
            ffmpeg = resolve_tool("ffmpeg")
            result = run_hidden(
                [ffmpeg, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            values: dict[str, float] = {}
            for key, raw in VOLUME_RE.findall(output):
                if raw.casefold() != "-inf":
                    values[key.casefold()] = float(raw)
            if "mean_volume" not in values and "max_volume" not in values:
                warning = "FFmpeg could not measure final audio volume."
                if "does not contain any stream" in output or "matches no streams" in output:
                    return AudioQualityInfo(has_audio=False, warnings=[warning])
                return AudioQualityInfo(has_audio=bool(has_audio), warnings=[warning])
            warnings: list[str] = []
            mean_volume = values.get("mean_volume")
            max_volume = values.get("max_volume")
            if mean_volume is not None and mean_volume < -35:
                warnings.append("Final mixed audio is very quiet.")
            if max_volume is not None and max_volume > -0.5:
                warnings.append("Final mixed audio is close to 0 dB and may clip.")
            return AudioQualityInfo(
                has_audio=True,
                peak_db=max_volume,
                mean_volume_db=mean_volume,
                max_volume_db=max_volume,
                warnings=warnings,
            )
        except (OSError, ValueError, DependencyError) as exc:
            return AudioQualityInfo(has_audio=bool(has_audio), warnings=[f"Audio analysis failed: {exc}"])
