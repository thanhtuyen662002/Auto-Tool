from __future__ import annotations

import shutil
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.modules.cache.cache_key_builder import CacheKeyBuilder, stable_hash
from app.modules.cache.cache_schema import CacheEvent, CacheRunStats
from app.modules.cache.cache_store import CacheStore
from app.schemas.project_schema import ProjectConfig
from app.utils.file_utils import ensure_dir


LogCallback = Callable[[str, str], None]


class CacheService:
    def __init__(
        self,
        base_dir: str | Path,
        enabled: bool = True,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.store = CacheStore(base_dir)
        self.keys = CacheKeyBuilder()
        self.enabled = enabled
        self.log_callback = log_callback
        self.stats = CacheRunStats(enabled=enabled)

    @classmethod
    def for_project(cls, config: ProjectConfig, log_callback: LogCallback | None = None) -> "CacheService":
        cache_dir = project_cache_dir(config)
        return cls(cache_dir, enabled=config.cache.enabled, log_callback=log_callback)

    def clear(self) -> None:
        self.store.invalidate_project_cache("project")

    def get_json(self, namespace: str, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        start = perf_counter()
        try:
            payload = self.store.get_json(key)
            self._record(namespace, key, bool(payload))
            return payload
        except Exception:
            self._record(namespace, key, False)
            return None
        finally:
            self._record_time("cache_read_seconds", perf_counter() - start)

    def set_json(self, key: str, data: dict[str, Any]) -> None:
        if not self.enabled:
            return
        start = perf_counter()
        try:
            self.store.set_json(key, data)
        except Exception as exc:
            self._log("warning", f"cache_write_failed: {exc}")
        finally:
            self._record_time("cache_write_seconds", perf_counter() - start)

    def get_file(self, namespace: str, key: str, output_path: str | Path | None = None) -> str | None:
        if not self.enabled:
            return None
        start = perf_counter()
        try:
            cached = self.store.get_file(key)
            hit = bool(cached)
            self._record(namespace, key, hit)
            if not cached:
                return None
            if output_path:
                target = Path(output_path)
                ensure_dir(target.parent)
                shutil.copy2(cached, target)
                return str(target)
            return cached
        except Exception as exc:
            self._record(namespace, key, False)
            self._log("warning", f"cache_read_failed: {exc}")
            return None
        finally:
            self._record_time("cache_read_seconds", perf_counter() - start)

    def set_file(self, key: str, source_path: str) -> str | None:
        if not self.enabled:
            return None
        start = perf_counter()
        try:
            return self.store.set_file(key, source_path)
        except Exception as exc:
            self._log("warning", f"cache_write_failed: {exc}")
            return None
        finally:
            self._record_time("cache_write_seconds", perf_counter() - start)

    def summary(self) -> dict[str, Any]:
        base = self.store.summary(enabled=self.enabled, hits=self.stats.hits, misses=self.stats.misses)
        base.update(self.stats.model_dump(mode="json", exclude={"events"}))
        base["items"] = self.store.summary()["items"]
        return base

    def output_cache_summary(
        self,
        *,
        segment_score_cache_hits: int = 0,
        crop_safety_cache_hits: int = 0,
        tts_cache_hit: bool = False,
        overlay_cache_hit: bool = False,
    ) -> dict[str, Any]:
        return {
            "segment_score_cache_hits": segment_score_cache_hits,
            "crop_safety_cache_hits": crop_safety_cache_hits,
            "tts_cache_hit": tts_cache_hit,
            "overlay_cache_hit": overlay_cache_hit,
        }

    def settings_hash(self, value: Any) -> str:
        return stable_hash(value)

    def _record(self, namespace: str, key: str, hit: bool) -> None:
        stat_prefix = _stat_prefix(namespace)
        if hit:
            self.stats.hits += 1
            hit_name = f"{stat_prefix}_hits"
            if hasattr(self.stats, hit_name):
                setattr(self.stats, hit_name, getattr(self.stats, hit_name) + 1)
            self.stats.cache_saved_estimated_seconds = round(self.stats.cache_saved_estimated_seconds + _estimated_saved_seconds(namespace), 3)
        else:
            self.stats.misses += 1
            miss_name = f"{stat_prefix}_misses"
            if hasattr(self.stats, miss_name):
                setattr(self.stats, miss_name, getattr(self.stats, miss_name) + 1)
        self.stats.events.append(CacheEvent(namespace=namespace, key=key, hit=hit))
        self._log("info", f"cache_{'hit' if hit else 'miss'}: {namespace}")

    def _record_time(self, key: str, seconds: float) -> None:
        current = getattr(self.stats, key)
        setattr(self.stats, key, round(current + max(0.0, seconds), 3))

    def _log(self, level: str, message: str) -> None:
        if self.log_callback:
            self.log_callback(level, message)


def project_cache_dir(config: ProjectConfig) -> Path:
    return Path(config.output_folder) / config.project_name / ".cache"


def cache_summary_for_project(config: ProjectConfig) -> dict[str, Any]:
    service = CacheService.for_project(config)
    return service.summary()


def _stat_prefix(namespace: str) -> str:
    aliases = {
        "media_metadata": "media_metadata",
        "segment_scores": "segment_score",
        "crop_safety": "crop_safety",
        "tts": "tts",
        "overlays": "overlay",
        "style_previews": "overlay",
    }
    return aliases.get(namespace, namespace)


def _estimated_saved_seconds(namespace: str) -> float:
    return {
        "media_metadata": 0.2,
        "segment_scores": 0.5,
        "crop_safety": 0.35,
        "tts": 2.0,
        "overlays": 0.2,
        "style_previews": 0.2,
    }.get(namespace, 0.1)
