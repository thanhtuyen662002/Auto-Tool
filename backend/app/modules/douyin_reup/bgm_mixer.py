from __future__ import annotations

import random
from pathlib import Path

SUPPORTED_BGM_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


class BGMMixer:
    def pick_bgm(self, music_folder: str | None, favorite_paths: list[str] | None = None) -> str | None:
        folder_hint = Path(music_folder).expanduser() if music_folder else None
        favorite_candidates = [
            path
            for path in _valid_audio_paths(favorite_paths or [])
            if folder_hint is None or not folder_hint.exists() or not folder_hint.is_dir() or _is_inside_folder(path, folder_hint)
        ]
        if favorite_candidates:
            return str(random.choice(favorite_candidates))

        if not music_folder:
            return None
        folder = Path(music_folder).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            return None
        candidates = sorted(
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_BGM_EXTENSIONS and path.stat().st_size > 0
        )
        if not candidates:
            return None
        return str(random.choice(candidates))

    def build_audio_filter(
        self,
        has_original_audio: bool,
        has_bgm: bool,
        original_audio_volume: float,
        bgm_volume: float,
        duration: float,
        bgm_input_index: int = 2,
    ) -> tuple[str, str | None]:
        filters: list[str] = []
        labels: list[str] = []

        if has_original_audio:
            filters.append(f"[0:a]volume={_clamp_volume(original_audio_volume):.3f}[a0]")
            labels.append("[a0]")

        if has_bgm:
            fade_out_start = max(0.0, float(duration) - 0.8)
            filters.append(
                f"[{bgm_input_index}:a]volume={_clamp_volume(bgm_volume):.3f},"
                f"afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.3f}:d=0.8[a1]"
            )
            labels.append("[a1]")

        if not labels:
            return "", None
        if len(labels) == 1:
            return ";".join(filters) + f";{labels[0]}anull[aout]", "[aout]"
        return ";".join(filters) + f";{''.join(labels)}amix=inputs=2:duration=first:dropout_transition=0[aout]", "[aout]"


def _clamp_volume(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _valid_audio_paths(paths: list[str]) -> list[Path]:
    candidates: list[Path] = []
    for item in paths:
        try:
            path = Path(item).expanduser().resolve()
        except OSError:
            continue
        if path.is_file() and path.suffix.lower() in SUPPORTED_BGM_EXTENSIONS and path.stat().st_size > 0:
            candidates.append(path)
    return sorted(candidates)


def _is_inside_folder(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False
