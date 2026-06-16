from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass


class ProviderQuotaCoolingDown(RuntimeError):
    """Raised when a provider key is temporarily paused after rate/quota errors."""


@dataclass
class _ProviderKeyState:
    last_request_at: float = 0.0
    cooldown_until: float = 0.0
    consecutive_quota_errors: int = 0


class ProviderQuotaManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[tuple[str, str], _ProviderKeyState] = {}

    def before_request(
        self,
        provider: str,
        key: str,
        *,
        min_interval_seconds: float = 0.0,
        wait_for_cooldown: bool = False,
    ) -> None:
        provider_id = _normalize_provider(provider)
        key_id = _key_id(key)
        now = time.monotonic()
        wait_seconds = 0.0
        with self._lock:
            state = self._state.setdefault((provider_id, key_id), _ProviderKeyState())
            if state.cooldown_until > now:
                remaining = state.cooldown_until - now
                if not wait_for_cooldown:
                    raise ProviderQuotaCoolingDown(
                        f"{provider_id} key {key_id} đang tạm nghỉ {remaining:.0f} giây do quota/rate-limit."
                    )
                wait_seconds = max(wait_seconds, remaining)
            if min_interval_seconds > 0 and state.last_request_at > 0:
                wait_seconds = max(wait_seconds, min_interval_seconds - (now - state.last_request_at))
            state.last_request_at = max(now + max(0.0, wait_seconds), state.last_request_at)

        if wait_seconds > 0:
            time.sleep(wait_seconds)

    def record_success(self, provider: str, key: str) -> None:
        provider_id = _normalize_provider(provider)
        key_id = _key_id(key)
        with self._lock:
            state = self._state.setdefault((provider_id, key_id), _ProviderKeyState())
            state.consecutive_quota_errors = 0

    def record_failure(
        self,
        provider: str,
        key: str,
        *,
        status_code: int | None = None,
        message: str = "",
        cooldown_seconds: int | float | None = None,
    ) -> bool:
        if not _is_quota_error(status_code, message):
            return False
        provider_id = _normalize_provider(provider)
        key_id = _key_id(key)
        cooldown = _cooldown_seconds(provider_id, cooldown_seconds)
        now = time.monotonic()
        with self._lock:
            state = self._state.setdefault((provider_id, key_id), _ProviderKeyState())
            state.consecutive_quota_errors += 1
            multiplier = min(4, state.consecutive_quota_errors)
            state.cooldown_until = max(state.cooldown_until, now + cooldown * multiplier)
        return True

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        now = time.monotonic()
        with self._lock:
            return {
                f"{provider}:{key_id}": {
                    "cooldown_remaining_seconds": max(0.0, state.cooldown_until - now),
                    "consecutive_quota_errors": state.consecutive_quota_errors,
                }
                for (provider, key_id), state in self._state.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


_GLOBAL_MANAGER = ProviderQuotaManager()


def get_provider_quota_manager() -> ProviderQuotaManager:
    return _GLOBAL_MANAGER


def _normalize_provider(provider: str) -> str:
    return (provider or "provider").strip().lower().replace(" ", "_")


def _key_id(key: str) -> str:
    value = (key or "default").strip() or "default"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _cooldown_seconds(provider: str, explicit: int | float | None) -> float:
    if explicit is not None:
        return max(1.0, float(explicit))
    env_name = f"AUTO_TOOL_{provider.upper()}_QUOTA_COOLDOWN_SECONDS"
    raw = os.getenv(env_name, "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return 60.0


def _is_quota_error(status_code: int | None, message: str) -> bool:
    if status_code == 429:
        return True
    text = (message or "").lower()
    return any(
        token in text
        for token in (
            "quota",
            "rate limit",
            "rate-limit",
            "resource exhausted",
            "too many requests",
            "requests per minute",
            "requests per day",
        )
    )
