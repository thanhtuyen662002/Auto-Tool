from __future__ import annotations

import multiprocessing as mp
import traceback
import tempfile
import json
import os
from collections.abc import Callable
from typing import Any


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
    
    try:
        process = ctx.Process(
            target=_isolated_process_entrypoint_file,
            args=(worker, args, kwargs or {}, temp_file_path),
            daemon=False,
        )
        process.start()
        process.join(timeout)

        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(5)
            raise IsolatedProcessTimeoutError(
                f"{stage_name} quá thời gian {timeout:.0f} giây nên đã dừng tiến trình con để batch tiếp tục chạy."
            )

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
        except Exception:
            pass


def _isolated_process_entrypoint_file(
    worker: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    temp_file_path: str,
) -> None:
    try:
        res = worker(*args, **kwargs)
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

