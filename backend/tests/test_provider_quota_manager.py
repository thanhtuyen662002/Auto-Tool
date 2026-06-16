from __future__ import annotations

import pytest

from app.modules.provider_quota import ProviderQuotaCoolingDown, ProviderQuotaManager


def test_provider_quota_marks_429_key_as_cooling_down() -> None:
    manager = ProviderQuotaManager()

    marked = manager.record_failure("gemini", "key-1", status_code=429, message="quota exceeded", cooldown_seconds=30)

    assert marked is True
    with pytest.raises(ProviderQuotaCoolingDown):
        manager.before_request("gemini", "key-1")


def test_provider_quota_ignores_non_quota_errors() -> None:
    manager = ProviderQuotaManager()

    marked = manager.record_failure("google_cloud_tts", "key-1", status_code=400, message="bad request")

    assert marked is False
    manager.before_request("google_cloud_tts", "key-1")


def test_provider_quota_success_clears_consecutive_error_count() -> None:
    manager = ProviderQuotaManager()
    manager.record_failure("gemini", "key-1", status_code=429, message="rate limit", cooldown_seconds=1)
    manager.record_success("gemini", "key-1")

    snapshot = manager.snapshot()
    assert next(iter(snapshot.values()))["consecutive_quota_errors"] == 0
