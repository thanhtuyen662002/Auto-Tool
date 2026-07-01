from __future__ import annotations

import os
import signal
import subprocess
import threading
from typing import Any

_TRACKED_PIDS: dict[int, str] = {}
_TRACKED_LOCK = threading.RLock()


def windows_no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    check = bool(kwargs.pop("check", False))
    timeout = kwargs.pop("timeout", None)
    input_data = kwargs.pop("input", None)
    capture_output = bool(kwargs.pop("capture_output", False))
    if input_data is not None and kwargs.get("stdin") is None:
        kwargs["stdin"] = subprocess.PIPE
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    process = popen_hidden(command, **kwargs)
    try:
        try:
            stdout, stderr = process.communicate(input_data, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            terminate_process_tree(process.pid, reason="subprocess timeout")
            stdout, stderr = process.communicate()
            exc.stdout = stdout
            exc.stderr = stderr
            raise
        completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check and completed.returncode:
            raise subprocess.CalledProcessError(completed.returncode, command, output=stdout, stderr=stderr)
        return completed
    finally:
        unregister_process_pid(process.pid)


def popen_hidden(command: list[str], **kwargs: Any) -> subprocess.Popen:
    track = bool(kwargs.pop("track", True))
    if os.name == "nt" and "creationflags" not in kwargs:
        kwargs["creationflags"] = windows_no_window_flags()
    elif os.name != "nt" and "start_new_session" not in kwargs:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    if track:
        register_process_pid(process.pid, _command_label(command))
    return process


def register_process_pid(pid: int | None, label: str | None = None) -> None:
    if not pid:
        return
    with _TRACKED_LOCK:
        _TRACKED_PIDS[int(pid)] = label or "subprocess"


def unregister_process_pid(pid: int | None) -> None:
    if not pid:
        return
    with _TRACKED_LOCK:
        _TRACKED_PIDS.pop(int(pid), None)


def terminate_process_tree(pid: int | None, *, reason: str | None = None, timeout_seconds: float = 5.0) -> bool:
    if not pid:
        return False
    target_pid = int(pid)
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(target_pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            timeout=max(1.0, timeout_seconds),
        )
        unregister_process_pid(target_pid)
        return result.returncode == 0
    try:
        os.killpg(target_pid, signal.SIGTERM)
    except ProcessLookupError:
        unregister_process_pid(target_pid)
        return False
    except OSError:
        try:
            os.kill(target_pid, signal.SIGTERM)
        except OSError:
            unregister_process_pid(target_pid)
            return False
    unregister_process_pid(target_pid)
    return True


def terminate_all_tracked_processes(*, reason: str | None = None) -> int:
    with _TRACKED_LOCK:
        pids = list(_TRACKED_PIDS)
    killed = 0
    for pid in pids:
        if terminate_process_tree(pid, reason=reason):
            killed += 1
    return killed


def tracked_process_count() -> int:
    with _TRACKED_LOCK:
        return len(_TRACKED_PIDS)


def _command_label(command: list[str]) -> str:
    return " ".join(str(part) for part in command[:4])
