from __future__ import annotations

from app.modules.cache.cache_service import CacheService


def test_cache_service_tracks_hits_misses_and_logs(tmp_path) -> None:
    logs: list[tuple[str, str]] = []
    service = CacheService(tmp_path / ".cache", log_callback=lambda level, message: logs.append((level, message)))

    assert service.get_json("media_metadata", "media_metadata/video") is None
    service.set_json("media_metadata/video", {"path": "video.mp4"})
    assert service.get_json("media_metadata", "media_metadata/video") == {"path": "video.mp4"}

    summary = service.summary()
    assert summary["misses"] == 1
    assert summary["hits"] == 1
    assert summary["media_metadata_misses"] == 1
    assert summary["media_metadata_hits"] == 1
    assert any("cache_miss: media_metadata" in message for _, message in logs)
    assert any("cache_hit: media_metadata" in message for _, message in logs)


def test_cache_service_unknown_namespace_does_not_crash(tmp_path) -> None:
    service = CacheService(tmp_path / ".cache")
    service.set_json("custom/item", {"ok": True})

    assert service.get_json("custom", "custom/item") == {"ok": True}
    assert service.summary()["hits"] == 1
