from __future__ import annotations

from pathlib import Path


def read_app_version() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "VERSION",
        Path(__file__).resolve().parents[1] / "VERSION",
        Path.cwd() / "VERSION",
    ]
    for path in candidates:
        try:
            if path.exists():
                version = path.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except OSError:
            continue
    return "unknown"


APP_VERSION = read_app_version()

