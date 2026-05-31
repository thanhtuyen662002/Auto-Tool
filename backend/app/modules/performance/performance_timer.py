from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator


class PerformanceTimer:
    def __init__(self) -> None:
        self.metrics: dict[str, float] = {}
        self._started_at = perf_counter()

    @contextmanager
    def measure(self, key: str) -> Iterator[None]:
        start = perf_counter()
        try:
            yield
        finally:
            self.record(key, perf_counter() - start)

    def record(self, key: str, seconds: float) -> None:
        current = self.metrics.get(key, 0.0)
        self.metrics[key] = round(current + max(0.0, seconds), 3)

    def total_seconds(self) -> float:
        return round(perf_counter() - self._started_at, 3)

    def snapshot(self, include_total: bool = True) -> dict[str, float]:
        payload = dict(self.metrics)
        if include_total:
            payload["total_seconds"] = self.total_seconds()
        return payload


def timed_call(metrics: dict[str, Any], key: str, action):
    start = perf_counter()
    try:
        return action()
    finally:
        metrics[key] = round(max(0.0, perf_counter() - start), 3)


def performance_summary(outputs: list[dict[str, Any]], total_runtime_seconds: float) -> dict[str, Any]:
    output_metrics: list[tuple[int, str, float]] = []
    for output in outputs:
        try:
            output_index = int(output.get("index") or 0)
        except (TypeError, ValueError):
            output_index = 0
        performance = output.get("performance") or {}
        if not isinstance(performance, dict):
            continue
        for key, value in performance.items():
            if key == "total_seconds":
                continue
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                continue
            output_metrics.append((output_index, key.removesuffix("_seconds"), seconds))

    successful_outputs = [item for item in outputs if item.get("status") in {"success", "warning"}]
    average = total_runtime_seconds / max(1, len(successful_outputs) or len(outputs) or 1)
    slowest = max(output_metrics, key=lambda item: item[2], default=(None, None, 0.0))
    return {
        "total_runtime_seconds": round(total_runtime_seconds, 3),
        "average_time_per_video": round(average, 3),
        "slowest_step": slowest[1],
        "slowest_output_index": slowest[0],
    }
