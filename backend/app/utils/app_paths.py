from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "AutoTool"

# Directory names used when bundling vendor tools via --add-data
VENDOR_FFMPEG_SUBDIR = "vendor/ffmpeg"
VENDOR_PIPER_SUBDIR  = "vendor/piper"


def backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return backend_dir().parent


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def bundle_dir() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle).resolve()
    return executable_dir()


def bundled_vendor_dir() -> Path:
    """Root of the vendor directory bundled via PyInstaller --add-data.

    When frozen: <_MEIPASS>/vendor/
    When running from source: <project_root>/backend/vendor/
    """
    candidates = [
        bundle_dir() / "vendor",
        executable_dir() / "vendor",
        backend_dir() / "vendor",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return bundle_dir() / "vendor"


def app_data_dir() -> Path:
    configured = os.getenv("AUTO_TOOL_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    if os.name == "nt":
        root = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return (Path(root) / APP_NAME).resolve()

    return (Path.home() / ".auto-tool").resolve()


def frontend_dist_dir() -> Path:
    configured = os.getenv("AUTO_TOOL_FRONTEND_DIST")
    if configured:
        return Path(configured).expanduser().resolve()

    candidates = [
        bundle_dir() / "frontend" / "dist",
        bundle_dir() / "dist",
        executable_dir() / "frontend" / "dist",
        executable_dir() / "dist",
        project_root() / "frontend" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate.resolve()
    return candidates[-1].resolve()


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        key = str(resolved).lower() if os.name == "nt" else str(resolved)
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result
