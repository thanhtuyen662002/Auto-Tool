from __future__ import annotations

import json
from datetime import datetime
import socket
import sys
import threading
import time
import webbrowser
import os
import multiprocessing as mp
import urllib.error
import urllib.request

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
from app.utils.app_paths import app_data_dir


logger = get_logger(__name__)
_STDIO_FALLBACK_HANDLES = []
_INSTANCE_LOCK_HANDLE = None


def main() -> int:
    _ensure_stdio_streams()
    load_local_env()
    configure_logging()
    local_config = LocalConfigService().load_config()
    host = _launcher_host(local_config.backend_host)
    preferred_port = _launcher_port(local_config.backend_port)
    existing_url = _existing_instance_url(host, preferred_port)
    if existing_url:
        logger.info("Auto Tool is already running at %s; opening the existing instance.", existing_url)
        if _open_browser_enabled(local_config.auto_open_browser):
            _open_browser(existing_url, delay_seconds=0.1)
        return 0

    lock_acquired = False
    if _single_instance_enabled():
        lock_acquired = _acquire_instance_lock()
        if not lock_acquired:
            if _wait_for_auto_tool_health(host, preferred_port, timeout_seconds=20.0):
                existing_url = _base_url(host, preferred_port)
                logger.info("Auto Tool finished starting at %s; opening the existing instance.", existing_url)
                if _open_browser_enabled(local_config.auto_open_browser):
                    _open_browser(existing_url, delay_seconds=0.1)
                return 0
            existing_url = _existing_instance_url(host, preferred_port)
            if existing_url:
                logger.info("Auto Tool is already running at %s; opening the existing instance.", existing_url)
                if _open_browser_enabled(local_config.auto_open_browser):
                    _open_browser(existing_url, delay_seconds=0.1)
                return 0
            logger.error("Another Auto Tool launcher is already starting. Refusing to start another hidden instance.")
            return 1

    try:
        return _run_server(local_config, host, preferred_port)
    finally:
        if lock_acquired:
            _release_instance_lock()


def _run_server(local_config, host: str, preferred_port: int) -> int:
    if not _port_available(preferred_port):
        if _wait_for_auto_tool_health(host, preferred_port, timeout_seconds=8.0):
            existing_url = _base_url(host, preferred_port)
            logger.info("Auto Tool became ready at %s; opening the existing instance.", existing_url)
            if _open_browser_enabled(local_config.auto_open_browser):
                _open_browser(existing_url, delay_seconds=0.1)
            return 0
        if _strict_port_enabled():
            logger.error(
                "Port %s is already in use, but it does not look like a ready Auto Tool server. "
                "Refusing to start another hidden instance.",
                preferred_port,
            )
            return 1
        logger.warning(
            "Port %s is already in use by another application. Auto Tool will start on another available port.",
            preferred_port,
        )
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

    url = _base_url(host, port)
    if _open_browser_enabled(local_config.auto_open_browser):
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    logger.info("Starting Auto Tool at %s", url)
    _write_server_state(host, port)
    try:
        uvicorn.run(create_app(), host=host, port=port, reload=False)
    finally:
        _clear_server_state_if_current()
    return 0


def _open_browser(url: str, delay_seconds: float = 1.0) -> None:
    time.sleep(max(0.0, float(delay_seconds)))
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


def _instance_lock_path() -> os.PathLike:
    return app_data_dir() / "launcher" / "instance.lock"


def _acquire_instance_lock() -> bool:
    global _INSTANCE_LOCK_HANDLE
    if _INSTANCE_LOCK_HANDLE is not None:
        return True
    path = _instance_lock_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handle = open(path, "a+b")
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii"))
        handle.flush()
        _INSTANCE_LOCK_HANDLE = handle
        return True
    except (OSError, BlockingIOError):
        try:
            handle.close()
        except Exception:
            pass
        return False


def _release_instance_lock() -> None:
    global _INSTANCE_LOCK_HANDLE
    handle = _INSTANCE_LOCK_HANDLE
    if handle is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.debug("Could not release launcher instance lock cleanly.", exc_info=True)
    finally:
        try:
            handle.close()
        finally:
            _INSTANCE_LOCK_HANDLE = None


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _health_url(host: str, port: int) -> str:
    return f"{_base_url(host, port)}/api/health"


def _existing_instance_url(default_host: str, default_port: int) -> str | None:
    state = _read_server_state()
    if state:
        host = str(state.get("host") or default_host)
        port = _safe_int(state.get("port"), default_port)
        if _auto_tool_health_ready(host, port):
            return _base_url(host, port)
    if _auto_tool_health_ready(default_host, default_port):
        return _base_url(default_host, default_port)
    return None


def _auto_tool_health_ready(host: str, port: int, timeout_seconds: float = 0.75) -> bool:
    try:
        with urllib.request.urlopen(_health_url(host, port), timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError, urllib.error.URLError, ValueError):
        return False
    capabilities = payload.get("capabilities") if isinstance(payload, dict) else None
    return bool(
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and isinstance(capabilities, dict)
        and capabilities.get("douyin_reup") is True
    )


def _wait_for_auto_tool_health(host: str, port: int, timeout_seconds: float = 8.0) -> bool:
    deadline = time.monotonic() + max(0.1, float(timeout_seconds))
    while time.monotonic() < deadline:
        if _auto_tool_health_ready(host, port, timeout_seconds=0.75):
            return True
        time.sleep(0.35)
    return False


def _server_state_path() -> os.PathLike:
    return app_data_dir() / "launcher" / "server_state.json"


def _read_server_state() -> dict[str, object] | None:
    path = _server_state_path()
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_server_state(host: str, port: int) -> None:
    path = _server_state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "host": host,
            "port": int(port),
            "url": _base_url(host, port),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError:
        logger.warning("Could not write launcher server state file.", exc_info=True)


def _clear_server_state_if_current() -> None:
    path = _server_state_path()
    state = _read_server_state()
    if not state or _safe_int(state.get("pid"), -1) != os.getpid():
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("Could not remove launcher server state file.", exc_info=True)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _open_browser_enabled(default: bool = True) -> bool:
    value = os.getenv("AUTO_TOOL_OPEN_BROWSER", "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _strict_port_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_STRICT_PORT", "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _single_instance_enabled() -> bool:
    value = os.getenv("AUTO_TOOL_SINGLE_INSTANCE", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _ensure_stdio_streams() -> None:
    """PyInstaller --noconsole sets stdout/stderr to None; Uvicorn expects streams."""
    if sys.stdout is not None and sys.stderr is not None:
        return

    log_dir = app_data_dir() / "logs" / "launcher"
    log_dir.mkdir(parents=True, exist_ok=True)

    if sys.stdout is None:
        stdout_file = (log_dir / "stdout.log").open("a", encoding="utf-8", buffering=1)
        _STDIO_FALLBACK_HANDLES.append(stdout_file)
        sys.stdout = stdout_file

    if sys.stderr is None:
        stderr_file = (log_dir / "stderr.log").open("a", encoding="utf-8", buffering=1)
        _STDIO_FALLBACK_HANDLES.append(stderr_file)
        sys.stderr = stderr_file


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
