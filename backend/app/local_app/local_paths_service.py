from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from app.local_app.local_config_schema import LocalRecentPaths
from app.local_app.local_config_service import LocalConfigService


RecentPathKind = Literal["source", "output", "music"]


class LocalPathsService:
    _FIELD_BY_KIND: dict[RecentPathKind, str] = {
        "source": "source_folders",
        "output": "output_folders",
        "music": "music_folders",
    }

    def __init__(self, config_service: LocalConfigService | None = None) -> None:
        self.config_service = config_service or LocalConfigService()
        self.root = self.config_service.root
        self.recent_paths_path = self.config_service.config_dir / "recent_paths.json"

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return path.resolve()

    def ensure_folder(self, value: str) -> Path:
        path = self.resolve_path(value)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def is_readable(self, value: str) -> bool:
        path = self.resolve_path(value)
        try:
            next(path.iterdir(), None) if path.is_dir() else path.open("rb").close()
            return path.exists()
        except OSError:
            return False

    def is_writable_folder(self, value: str) -> bool:
        try:
            path = self.ensure_folder(value)
            probe = path / ".auto-tool-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def get_recent_paths(self) -> LocalRecentPaths:
        self.config_service.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.recent_paths_path.exists():
            return self._save_recent_paths(LocalRecentPaths())
        try:
            payload = json.loads(self.recent_paths_path.read_text(encoding="utf-8"))
            return LocalRecentPaths.model_validate(payload)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return self._save_recent_paths(LocalRecentPaths())

    def add_recent_path(self, kind: RecentPathKind, value: str) -> LocalRecentPaths:
        path = str(self.resolve_path(value))
        recent = self.get_recent_paths()
        field = self._FIELD_BY_KIND[kind]
        current = list(getattr(recent, field))
        normalized = [item for item in current if item.casefold() != path.casefold()]
        limit = self.config_service.load_config().max_recent_items
        setattr(recent, field, [path, *normalized][:limit])
        return self._save_recent_paths(recent)

    def _save_recent_paths(self, recent: LocalRecentPaths) -> LocalRecentPaths:
        self.config_service.config_dir.mkdir(parents=True, exist_ok=True)
        self.recent_paths_path.write_text(
            json.dumps(recent.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return recent
