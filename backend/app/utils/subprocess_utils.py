from __future__ import annotations

import os
import subprocess
from typing import Any


def windows_no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def run_hidden(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    if os.name == "nt" and "creationflags" not in kwargs:
        kwargs["creationflags"] = windows_no_window_flags()
    return subprocess.run(command, **kwargs)


def popen_hidden(command: list[str], **kwargs: Any) -> subprocess.Popen:
    if os.name == "nt" and "creationflags" not in kwargs:
        kwargs["creationflags"] = windows_no_window_flags()
    return subprocess.Popen(command, **kwargs)
