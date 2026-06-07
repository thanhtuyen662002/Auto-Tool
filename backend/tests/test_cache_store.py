from __future__ import annotations

from app.modules.cache.cache_store import CacheStore


def test_cache_store_reads_and_writes_json(tmp_path) -> None:
    store = CacheStore(tmp_path)

    store.set_json("media_metadata/abc", {"duration": 12})

    assert store.get_json("media_metadata/abc") == {"duration": 12}


def test_cache_store_ignores_corrupt_json(tmp_path) -> None:
    store = CacheStore(tmp_path)
    corrupt_path = tmp_path / "media_metadata" / "bad.json"
    corrupt_path.parent.mkdir(parents=True)
    corrupt_path.write_text("{not-json", encoding="utf-8")

    assert store.get_json("media_metadata/bad") is None


def test_cache_store_reads_and_writes_cached_file(tmp_path) -> None:
    store = CacheStore(tmp_path / ".cache")
    source = tmp_path / "voice.wav"
    source.write_bytes(b"voice")

    cached_path = store.set_file("tts/voice-key", str(source))

    assert cached_path
    assert store.get_file("tts/voice-key") == cached_path


def test_cache_store_clear_removes_cache_items(tmp_path) -> None:
    store = CacheStore(tmp_path / ".cache")
    store.set_json("segment_scores/score-key", {"score": 0.8})

    store.invalidate_project_cache("project")

    assert not list((tmp_path / ".cache").rglob("*.json"))
