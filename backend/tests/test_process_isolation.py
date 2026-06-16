from __future__ import annotations

import time

import pytest

from app.utils.process_isolation import IsolatedProcessTimeoutError, run_in_isolated_process


def _return_payload(value: str) -> dict[str, str]:
    return {"value": value}


def _sleep_long() -> None:
    time.sleep(5)


def test_run_in_isolated_process_returns_payload() -> None:
    result = run_in_isolated_process(
        _return_payload,
        "ok",
        timeout_seconds=5,
        stage_name="test_stage",
    )

    assert result == {"value": "ok"}


def test_run_in_isolated_process_hard_times_out() -> None:
    started = time.monotonic()

    with pytest.raises(IsolatedProcessTimeoutError) as exc:
        run_in_isolated_process(
            _sleep_long,
            timeout_seconds=1,
            stage_name="slow_stage",
        )

    assert time.monotonic() - started < 4
    assert "slow_stage" in str(exc.value)
