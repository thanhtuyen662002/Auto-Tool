from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from app.modules.queue_control.queue_control_schema import BatchResourcePlan


class StageGate:
    """Named semaphores for resource-heavy pipeline stages.

    The current queue still runs jobs sequentially. This small gate gives the
    next worker-pool step a single place to enforce stage-specific limits
    instead of scattering semaphores across ASR/OCR/render/TTS modules.
    """

    def __init__(self, plan: BatchResourcePlan | None = None) -> None:
        limits = dict(plan.stage_limits if plan else {})
        if not limits:
            limits = {"asr": 1, "ocr": 1, "render": 1, "tts": 1, "translation": 1}
        self._limits = {stage: max(1, int(limit)) for stage, limit in limits.items()}
        self._semaphores = {
            stage: threading.BoundedSemaphore(value=limit)
            for stage, limit in self._limits.items()
        }
        self._default = threading.BoundedSemaphore(value=1)

    @contextmanager
    def acquire(self, stage: str) -> Iterator[None]:
        semaphore = self._semaphores.get(stage, self._default)
        semaphore.acquire()
        try:
            yield
        finally:
            semaphore.release()

    def limit_for(self, stage: str) -> int:
        return self._limits.get(stage, 1)
