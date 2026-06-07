from __future__ import annotations

from app.modules.cache.cache_key_builder import CacheKeyBuilder


def test_same_file_without_changes_has_same_media_cache_key(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-data")
    builder = CacheKeyBuilder()

    first_key = builder.build_media_key(str(source))
    second_key = builder.build_media_key(str(source))

    assert first_key == second_key


def test_file_size_change_invalidates_media_cache_key(tmp_path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-data")
    builder = CacheKeyBuilder()
    first_key = builder.build_media_key(str(source))

    source.write_bytes(b"video-data-updated")
    second_key = builder.build_media_key(str(source))

    assert first_key != second_key
