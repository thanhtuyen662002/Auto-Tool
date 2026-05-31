from __future__ import annotations

import os
from pathlib import Path

from app.utils.app_paths import backend_dir, executable_dir, project_root, unique_paths


def load_local_env() -> None:
    for env_file in unique_paths(
        [
            executable_dir() / ".env",
            backend_dir() / ".env",
            project_root() / ".env",
        ]
    ):
        _load_env_file(env_file)


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
