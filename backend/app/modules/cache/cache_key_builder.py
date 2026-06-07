from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class CacheKeyBuilder:
    def build_media_key(self, file_path: str) -> str:
        return _key("media_metadata", {"file": _file_signature(file_path)})

    def build_segment_score_key(self, source_path: str, start: float, end: float, settings_hash: str) -> str:
        return _key(
            "segment_scores",
            {
                "file": _file_signature(source_path),
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "settings_hash": settings_hash,
            },
        )

    def build_crop_safety_key(
        self,
        source_path: str,
        start: float,
        end: float,
        target_resolution: str,
        overlay_ratio: float,
        *,
        zoom_motion: int | None = None,
        crop_mode: str | None = None,
    ) -> str:
        return _key(
            "crop_safety",
            {
                "file": _file_signature(source_path),
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "target_resolution": target_resolution,
                "overlay_ratio": round(float(overlay_ratio), 4),
                "zoom_motion": zoom_motion,
                "crop_mode": crop_mode,
            },
        )

    def build_tts_key(
        self,
        text: str,
        voice: str,
        provider: str,
        rate: str,
        *,
        pitch: str = "",
        volume: str = "",
        output_format: str = "",
        target_duration: float | None = None,
    ) -> str:
        return _key(
            "tts",
            {
                "text": " ".join(text.split()),
                "voice": voice,
                "provider": provider.strip().lower().replace("-", "_"),
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "output_format": output_format.lower().lstrip("."),
                "target_duration": round(float(target_duration), 3) if target_duration is not None else None,
            },
        )

    def build_overlay_key(
        self,
        preset_id: str,
        resolution: str,
        *,
        custom_overrides_hash: str = "",
    ) -> str:
        return _key(
            "overlays",
            {
                "preset_id": preset_id,
                "resolution": resolution.lower(),
                "custom_overrides_hash": custom_overrides_hash,
            },
        )

    def build_style_preview_key(self, preset_id: str, resolution: str, sample_text: str) -> str:
        return _key(
            "style_previews",
            {
                "preset_id": preset_id,
                "resolution": resolution.lower(),
                "sample_text": " ".join(sample_text.split()),
            },
        )


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _key(namespace: str, payload: dict[str, Any]) -> str:
    return f"{namespace}/{stable_hash(payload)}"


def _file_signature(file_path: str) -> dict[str, Any]:
    target = Path(file_path).expanduser().resolve()
    try:
        stat = target.stat()
        return {
            "path": str(target),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    except OSError:
        return {
            "path": str(target),
            "size": None,
            "mtime_ns": None,
        }

