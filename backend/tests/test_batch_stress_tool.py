from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_batch_stress_tool_runs_small_batch() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.tools.batch_stress_test",
            "--items",
            "25",
            "--failed-every",
            "10",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=Path(__file__).resolve().parents[1],
    )

    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["items"] == 25
    assert report["completed"] == 23
    assert report["failed"] == 2
