from __future__ import annotations

import random
from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_media_duration
from app.schemas.project_schema import ProjectConfig
from app.utils.logger import get_logger


logger = get_logger(__name__)


class MusicSelector:
    supported_extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def select_music(self, config: ProjectConfig, output_index: int) -> str | None:
        self.warnings = []
        if not config.music.enabled:
            return None

        if config.music.source_file:
            return self._validate_file(Path(config.music.source_file))

        if not config.music.source_folder:
            self._warn("Music is enabled but neither music.source_file nor music.source_folder is configured.")
            return None

        folder = Path(config.music.source_folder)
        if not folder.exists() or not folder.is_dir():
            self._warn(f"Music folder does not exist or is not a folder: {folder}")
            return None

        candidates = [
            path
            for path in sorted(folder.rglob("*"))
            if path.is_file() and path.suffix.lower() in self.supported_extensions
        ]
        valid_candidates = [path for path in candidates if self._is_valid_audio(path)]
        if not valid_candidates:
            self._warn(f"No valid music files found in: {folder}")
            return None

        rng = random.Random(90_000 + output_index)
        return str(rng.choice(valid_candidates).resolve())

    def _validate_file(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            self._warn(f"Configured music file does not exist: {path}")
            return None
        if path.suffix.lower() not in self.supported_extensions:
            self._warn(f"Unsupported music file extension: {path}")
            return None
        if not self._is_valid_audio(path):
            return None
        return str(path.resolve())

    def _is_valid_audio(self, path: Path) -> bool:
        try:
            probe_media_duration(str(path))
        except Exception as exc:
            self._warn(f"Skipping invalid music file {path}: {exc}")
            return False
        return True

    def _warn(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)
