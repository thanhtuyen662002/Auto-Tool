from __future__ import annotations

import threading
import time

from app.modules.queue_control import BatchResourcePlan, StageGate


def test_stage_gate_exposes_stage_limits() -> None:
    gate = StageGate(BatchResourcePlan(stage_limits={"asr": 1, "render": 2}))

    assert gate.limit_for("asr") == 1
    assert gate.limit_for("render") == 2
    assert gate.limit_for("unknown") == 1


def test_stage_gate_serializes_same_stage_when_limit_is_one() -> None:
    gate = StageGate(BatchResourcePlan(stage_limits={"render": 1}))
    events: list[str] = []

    def worker(name: str) -> None:
        with gate.acquire("render"):
            events.append(f"{name}:start")
            time.sleep(0.02)
            events.append(f"{name}:end")

    first = threading.Thread(target=worker, args=("a",))
    second = threading.Thread(target=worker, args=("b",))
    first.start()
    second.start()
    first.join()
    second.join()

    assert events in (
        ["a:start", "a:end", "b:start", "b:end"],
        ["b:start", "b:end", "a:start", "a:end"],
    )
