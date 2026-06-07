from __future__ import annotations

from pathlib import Path

from app.modules.cache.cache_service import CacheService
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.tts.tts_schema import TTSResult, TTSSettings
from app.modules.voice_generator import voice_generator
from app.modules.voice_generator.voice_generator import VoiceGenerator


class CountingTTSManager:
    def __init__(self) -> None:
        self.calls = 0

    def generate_voice(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        self.calls += 1
        Path(output_path).write_bytes(f"voice-{self.calls}-{text}".encode("utf-8"))
        return TTSResult(
            provider=settings.provider,
            output_path=output_path,
            duration=1.0,
            format=Path(output_path).suffix.lower().lstrip(".") or settings.output_format,
            success=True,
        )


def test_tts_reuses_cached_audio_when_text_is_unchanged(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(voice_generator, "probe_media_duration", lambda path: 1.0)
    cache_service = CacheService(tmp_path / ".cache")
    manager = CountingTTSManager()
    script = _script("Một câu giới thiệu sản phẩm.")

    first = VoiceGenerator(manager, cache_service=cache_service).generate_voiceover(
        script,
        str(tmp_path / "first"),
        filename="voice.wav",
    )
    second_generator = VoiceGenerator(manager, cache_service=cache_service)
    second = second_generator.generate_voiceover(
        script,
        str(tmp_path / "second"),
        filename="voice.wav",
    )

    assert manager.calls == 1
    assert Path(first).read_bytes() == Path(second).read_bytes()
    assert second_generator.last_cache_hit is True


def test_tts_generates_new_audio_when_text_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(voice_generator, "probe_media_duration", lambda path: 1.0)
    cache_service = CacheService(tmp_path / ".cache")
    manager = CountingTTSManager()

    VoiceGenerator(manager, cache_service=cache_service).generate_voiceover(
        _script("Một câu giới thiệu sản phẩm."),
        str(tmp_path / "first"),
        filename="voice.wav",
    )
    second_generator = VoiceGenerator(manager, cache_service=cache_service)
    second_generator.generate_voiceover(
        _script("Một câu giới thiệu sản phẩm đã thay đổi."),
        str(tmp_path / "second"),
        filename="voice.wav",
    )

    assert manager.calls == 2
    assert second_generator.last_cache_hit is False


def _script(text: str) -> ProductVideoScript:
    return ProductVideoScript.model_validate(
        {
            "hook": "Hook",
            "voiceover": [{"time_hint": "0-3s", "text": text}],
            "subtitles": [{"start_hint": 0, "end_hint": 3, "text": text}],
            "cta": "Xem ngay",
            "caption": "Caption",
            "hashtags": ["#review"],
        }
    )
