from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)


class CacheStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = ensure_dir(base_dir)

    def get_json(self, key: str) -> dict[str, Any] | None:
        path = self._path_for_key(key, ".json")
        try:
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Bỏ qua cache JSON bị lỗi %s: %s", path, exc)
            return None

    def set_json(self, key: str, data: dict[str, Any]) -> None:
        path = self._path_for_key(key, ".json")
        ensure_dir(path.parent)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_file(self, key: str) -> str | None:
        meta = self.get_json(key)
        if not meta:
            return None
        cached_path = meta.get("cached_path")
        if not cached_path:
            return None
        path = Path(str(cached_path))
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            return str(path)
        return None

    def set_file(self, key: str, source_path: str) -> str:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Cannot cache missing file: {source}")
        target = self._path_for_key(key, source.suffix or ".bin")
        ensure_dir(target.parent)
        shutil.copy2(source, target)
        self.set_json(
            key,
            {
                "cached_path": str(target),
                "source_path": str(source),
                "source_size": source.stat().st_size,
                "source_mtime_ns": source.stat().st_mtime_ns,
            },
        )
        return str(target)

    def invalidate_project_cache(self, project_id: str) -> None:
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)
        ensure_dir(self.base_dir)

    def summary(self, enabled: bool = True, hits: int = 0, misses: int = 0) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "hits": hits,
            "misses": misses,
            "cache_size_mb": round(_directory_size(self.base_dir) / (1024 * 1024), 3),
            "items": _count_items(self.base_dir),
        }

    def _path_for_key(self, key: str, suffix: str) -> Path:
        parts = [_safe_part(part) for part in key.replace("\\", "/").split("/") if part]
        if not parts:
            raise ValueError("Cache key cannot be empty.")
        return self.base_dir.joinpath(*parts).with_suffix(suffix)


def _safe_part(value: str) -> str:
    allowed = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        else:
            allowed.append("_")
    cleaned = "".join(allowed).strip("_")
    return cleaned or "cache"


def _directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _count_items(path: Path) -> dict[str, int]:
    items: dict[str, int] = {}
    if not path.exists():
        return items
    for child in path.iterdir():
        if not child.is_dir():
            continue
        count = sum(1 for item in child.glob("*.json") if item.is_file())
        items[child.name] = count
    return items

