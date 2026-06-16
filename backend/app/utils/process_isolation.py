from __future__ import annotations

import multiprocessing as mp
import queue
import traceback
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
    result_queue: mp.Queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_isolated_process_entrypoint,
        args=(worker, args, kwargs or {}, result_queue),
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

    try:
        status, payload = result_queue.get_nowait()
    except queue.Empty as exc:
        exit_code = process.exitcode
        raise IsolatedProcessError(f"{stage_name} kết thúc nhưng không trả kết quả. Exit code: {exit_code}.") from exc

    if status == "ok":
        return payload

    message = str(payload.get("message") or f"{stage_name} thất bại trong tiến trình con.")
    detail = str(payload.get("traceback") or "").strip()
    if detail:
        message = f"{message}\n{detail}"
    raise IsolatedProcessError(message)


def _isolated_process_entrypoint(
    worker: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result_queue: mp.Queue,
) -> None:
    try:
        result_queue.put(("ok", worker(*args, **kwargs)))
    except BaseException as exc:  # noqa: BLE001 - child must report every failure to parent.
        result_queue.put(
            (
                "error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(limit=20),
                },
            )
        )
