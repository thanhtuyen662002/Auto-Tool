from __future__ import annotations

import socket
import threading
import time
import webbrowser
import os
import multiprocessing as mp

import uvicorn

from app.api import create_app
from app.local_app import LocalConfigService
from app.utils.dependency_manager import (
    DEFAULT_OCR_PROVIDER,
    RuntimeDependencyReport,
    ensure_runtime_dependencies,
    start_background_dependency_warmup,
)
from app.utils.env_loader import load_local_env
from app.utils.logger import configure_logging, get_logger


logger = get_logger(__name__)


def main() -> int:
    load_local_env()
    configure_logging()
    local_config = LocalConfigService().load_config()
    host = _launcher_host(local_config.backend_host)
    preferred_port = _launcher_port(local_config.backend_port)
    if _strict_port_enabled() and not _port_available(preferred_port):
        logger.error("Port %s is already in use. Stop the existing server and try again.", preferred_port)
        return 1
    port = _find_available_port(preferred_port)

    try:
        report = ensure_runtime_dependencies(auto_install=None, include_piper=True)
    except Exception as exc:
        logger.warning("Runtime dependency check failed: %s", exc)
        report = RuntimeDependencyReport(ffmpeg_path=None, ffprobe_path=None, auto_installed=False)
    logger.info("FFmpeg: %s", report.ffmpeg_path or "not found")
    logger.info("FFprobe: %s", report.ffprobe_path or "not found")
    logger.info("Piper: %s", report.piper_path or "not found")
    logger.info("Piper model: %s", report.piper_model_path or "not found")
    for warning in report.warnings:
        logger.warning(warning)
    start_background_dependency_warmup(
        include_piper=False,
        include_ocr=True,
        ocr_provider=os.getenv("AUTO_TOOL_OCR_PROVIDER", DEFAULT_OCR_PROVIDER),
        warmup_ocr_models=True,
    )

    url = f"http://{host}:{port}"
    if _open_browser_enabled(local_config.auto_open_browser):
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    logger.info("Starting Auto Tool at %s", url)
    uvicorn.run(create_app(), host=host, port=port, reload=False)
    return 0


def _open_browser(url: str) -> None:
    time.sleep(1.0)
    webbrowser.open(url)


def _launcher_host(default: str) -> str:
    value = os.getenv("AUTO_TOOL_HOST", "").strip()
    return value or default


def _launcher_port(default: int) -> int:
    value = os.getenv("AUTO_TOOL_PORT", "").strip()
    if not value:
        return int(default)
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid AUTO_TOOL_PORT=%r; using %s.", value, default)
        return int(default)


def _find_available_port(preferred: int) -> int:
    if _port_available(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _open_browser_enabled(default: bool = True) -> bool:
    value = os.getenv("AUTO_TOOL_OPEN_BROWSER", "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _strict_port_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_STRICT_PORT", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
