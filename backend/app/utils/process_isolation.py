from __future__ import annotations

import multiprocessing as mp
import traceback
import tempfile
import json
import os
import inspect
import time
from collections.abc import Callable
from typing import Any

from app.utils.subprocess_utils import register_process_pid, terminate_process_tree, unregister_process_pid


class IsolatedProcessError(RuntimeError):
    """Raised when an isolated worker exits without a usable result."""


class IsolatedProcessTimeoutError(IsolatedProcessError):
    """Raised when an isolated worker exceeds its hard timeout."""


def run_in_isolated_process(
    worker: Callable[..., Any],
    *args: Any,
    timeout_seconds: int | float,
    stage_name: str,
    kwargs: dict[str, Any] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    progress_poll_interval_seconds: float = 1.0,
) -> Any:
    """
    Run a picklable top-level worker in a fresh Python process.

    This is intentionally stricter than a normal timeout inside Python code:
    if a native dependency such as OCR/ASR hangs, the parent can terminate the
    whole worker process and keep the batch alive.
    """

    timeout = max(1.0, float(timeout_seconds))
    ctx = mp.get_context("spawn")
    
    # Create a temporary JSON file to safely exchange result data without multiprocessing Queue deadlock
    fd, temp_file_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    progress_fd, progress_file_path = tempfile.mkstemp(suffix=".progress.json")
    os.close(progress_fd)
    
    try:
        process = ctx.Process(
            target=_isolated_process_entrypoint_file,
            args=(worker, args, kwargs or {}, temp_file_path, progress_file_path),
            daemon=False,
        )
        process.start()
        register_process_pid(process.pid, stage_name)

        deadline = time.monotonic() + timeout
        last_progress_marker: tuple[float, int] | None = None
        while process.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            process.join(min(max(0.1, progress_poll_interval_seconds), remaining))
            last_progress_marker = _emit_progress_if_changed(
                progress_file_path,
                progress_callback,
                last_progress_marker,
            )

        if process.is_alive():
            terminate_process_tree(process.pid, reason=f"{stage_name} timeout")
            process.join(5)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(5)
            raise IsolatedProcessTimeoutError(
                f"{stage_name} quá thời gian {timeout:.0f} giây nên đã dừng tiến trình con để batch tiếp tục chạy."
            )
        unregister_process_pid(process.pid)
        _emit_progress_if_changed(progress_file_path, progress_callback, last_progress_marker)

        exit_code = process.exitcode
        if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
            raise IsolatedProcessError(f"{stage_name} kết thúc nhưng không trả kết quả. Exit code: {exit_code}.")

        with open(temp_file_path, "r", encoding="utf-8") as f:
            status, payload = json.load(f)

        if status == "ok":
            return payload

        message = str(payload.get("message") or f"{stage_name} thất bại trong tiến trình con.")
        detail = str(payload.get("traceback") or "").strip()
        if detail:
            message = f"{message}\n{detail}"
        raise IsolatedProcessError(message)
        
    finally:
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if os.path.exists(progress_file_path):
                os.remove(progress_file_path)
        except Exception:
            pass


def _isolated_process_entrypoint_file(
    worker: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    temp_file_path: str,
    progress_file_path: str,
) -> None:
    try:
        worker_kwargs = dict(kwargs or {})
        try:
            parameters = inspect.signature(worker).parameters
        except (TypeError, ValueError):
            parameters = {}
        if "progress_callback" in parameters and "progress_callback" not in worker_kwargs:
            worker_kwargs["progress_callback"] = _file_progress_callback(progress_file_path)
        res = worker(*args, **worker_kwargs)
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(("ok", res), f, ensure_ascii=False)
    except BaseException as exc:  # noqa: BLE001 - child must report every failure to parent.
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(
                (
                    "error",
                    {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(limit=20),
                    },
                ),
                f,
                ensure_ascii=False,
            )


def _file_progress_callback(progress_file_path: str) -> Callable[[dict[str, Any]], None]:
    def callback(payload: dict[str, Any]) -> None:
        try:
            serializable = dict(payload or {})
            serializable["reported_at"] = time.time()
            tmp_path = f"{progress_file_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False)
            os.replace(tmp_path, progress_file_path)
        except Exception:
            pass

    return callback


def _emit_progress_if_changed(
    progress_file_path: str,
    callback: Callable[[dict[str, Any]], None] | None,
    last_marker: tuple[float, int] | None,
) -> tuple[float, int] | None:
    if callback is None:
        return last_marker
    try:
        stat = os.stat(progress_file_path)
    except OSError:
        return last_marker
    marker = (stat.st_mtime, stat.st_size)
    if last_marker == marker or stat.st_size <= 0:
        return last_marker
    try:
        with open(progress_file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return last_marker
    if isinstance(payload, dict):
        callback(payload)
    return marker

