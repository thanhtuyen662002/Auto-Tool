from __future__ import annotations

import subprocess
from pathlib import Path

from app.utils.dependency_manager import DependencyError, resolve_tool


class SourceMediaThumbnailService:
    def generate_thumbnail(
        self,
        video_path: str,
        output_folder: str,
        at_second: float = 1.0,
        media_id: str | None = None,
    ) -> str | None:
        source = Path(video_path).expanduser().resolve()
        if not source.exists():
            return None
        output_dir = Path(output_folder).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = media_id or source.stem
        target = output_dir / f"{safe_name}.jpg"
        if target.exists() and target.stat().st_size > 0:
            return str(target)
        try:
            ffmpeg = resolve_tool("ffmpeg")
            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-ss",
                    str(max(0.0, at_second)),
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(target),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except (DependencyError, FileNotFoundError):
            return None
        if result.returncode != 0 or not target.exists() or target.stat().st_size <= 0:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            return None
        return str(target)
