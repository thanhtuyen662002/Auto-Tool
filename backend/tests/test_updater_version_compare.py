from __future__ import annotations

from app.utils.updater import is_newer


def test_release_version_is_newer_than_prerelease() -> None:
    assert is_newer("1.0.0", "1.0.0-rc1") is True


def test_prerelease_numbers_are_ordered() -> None:
    assert is_newer("1.0.0-rc2", "1.0.0-rc1") is True
    assert is_newer("1.0.0-rc1", "1.0.0-rc2") is False


def test_patch_version_is_newer_than_previous_core() -> None:
    assert is_newer("1.0.1", "1.0.0-rc1") is True


def test_prerelease_is_not_newer_than_release_with_same_core() -> None:
    assert is_newer("1.0.1-rc1", "1.0.1") is False
