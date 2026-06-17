from __future__ import annotations

import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.local_app.local_config_schema import LocalAppConfig
from app.utils.app_paths import app_data_dir


def project_root() -> Path:
    configured = os.getenv("AUTO_TOOL_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


class LocalConfigService:
    def __init__(self, root: Path | None = None) -> None:
        explicit_config_dir = os.getenv("AUTO_TOOL_LOCAL_CONFIG_DIR")
        self.uses_explicit_root = root is not None
        if root is not None:
            self.root = root.resolve()
            self.config_dir = self.root / "config"
        elif explicit_config_dir:
            self.root = Path(explicit_config_dir).expanduser().resolve().parent
            self.config_dir = Path(explicit_config_dir).expanduser().resolve()
        else:
            self.root = app_data_dir().resolve()
            self.config_dir = self.root / "config"
        self.config_path = self.config_dir / "local_app_config.json"
        self.legacy_config_path = project_root() / "config" / "local_app_config.json"

    def ensure_config_exists(self) -> Path:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_config()
        if not self.config_path.exists():
            self.save_config(LocalAppConfig())
        return self.config_path

    def load_config(self) -> LocalAppConfig:
        self.ensure_config_exists()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            return LocalAppConfig.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            self._backup_invalid_config()
            defaults = LocalAppConfig()
            self.save_config(defaults)
            return defaults

    def save_config(self, config: LocalAppConfig) -> LocalAppConfig:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config

    def reset_config(self) -> LocalAppConfig:
        defaults = LocalAppConfig()
        return self.save_config(defaults)

    def _backup_invalid_config(self) -> None:
        if not self.config_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.config_path.with_name(f"{self.config_path.stem}.invalid-{timestamp}.bak")
        try:
            self.config_path.replace(backup_path)
        except OSError:
            pass

    def _migrate_legacy_config(self) -> None:
        if self.config_path.exists() or not self.legacy_config_path.exists():
            return
        try:
            if self.legacy_config_path.resolve() == self.config_path.resolve():
                return
        except OSError:
            return
        try:
            shutil.copy2(self.legacy_config_path, self.config_path)
        except OSError:
            pass
