from __future__ import annotations

from app.modules.douyin_reup.bgm_mixer import BGMMixer


def test_bgm_mixer_picks_supported_music_file(tmp_path):
    (tmp_path / "readme.txt").write_text("ignore", encoding="utf-8")
    music = tmp_path / "music.mp3"
    music.write_bytes(b"mp3")

    picked = BGMMixer().pick_bgm(str(tmp_path))

    assert picked == str(music.resolve())


def test_bgm_mixer_returns_none_for_missing_folder(tmp_path):
    assert BGMMixer().pick_bgm(str(tmp_path / "missing")) is None


def test_bgm_mixer_builds_audio_filter_for_original_and_bgm():
    filter_complex, label = BGMMixer().build_audio_filter(
        has_original_audio=True,
        has_bgm=True,
        original_audio_volume=0.8,
        bgm_volume=0.2,
        duration=10,
        bgm_input_index=2,
    )

    assert label == "[aout]"
    assert "[0:a]volume=0.800" in filter_complex
    assert "[2:a]volume=0.200" in filter_complex
    assert "amix=inputs=2" in filter_complex
