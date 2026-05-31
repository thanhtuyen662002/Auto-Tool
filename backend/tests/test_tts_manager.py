from __future__ import annotations

from pathlib import Path

from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_manager import TTSManager
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class FakeProvider(BaseTTSProvider):
    def __init__(self, provider_id: str, should_fail: bool = False) -> None:
        self.id = provider_id
        self.name = provider_id
        self.online = False
        self.should_fail = should_fail
        self.calls = 0

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        self.calls += 1
        if self.should_fail:
            raise TTSProviderError(f"{self.id} failed intentionally")
        Path(output_path).write_bytes(b"voice")
        return TTSResult(
            provider=self.id,
            output_path=output_path,
            duration=1.25,
            format="wav",
            success=True,
        )


def test_tts_manager_uses_primary_provider(tmp_path):
    primary = FakeProvider("edge_tts")
    fallback = FakeProvider("piper")
    manager = TTSManager({"edge_tts": primary, "piper": fallback, "gtts": FakeProvider("gtts"), "silent": FakeProvider("silent")})

    result = manager.generate_voice("Xin chao", str(tmp_path / "voice.wav"), TTSSettings(provider="edge_tts"))

    assert result.provider == "edge_tts"
    assert result.duration == 1.25
    assert result.fallback_used is False
    assert primary.calls == 1
    assert fallback.calls == 0


def test_tts_manager_falls_back_when_primary_fails(tmp_path):
    primary = FakeProvider("edge_tts", should_fail=True)
    fallback = FakeProvider("piper")
    manager = TTSManager({"edge_tts": primary, "piper": fallback, "gtts": FakeProvider("gtts"), "silent": FakeProvider("silent")})

    result = manager.generate_voice(
        "Xin chao",
        str(tmp_path / "voice.wav"),
        TTSSettings(provider="edge_tts", fallback_provider="piper"),
    )

    assert result.provider == "piper"
    assert result.fallback_used is True
    assert any("edge_tts failed intentionally" in warning for warning in result.warnings)


def test_tts_manager_uses_silent_when_other_providers_fail(tmp_path):
    manager = TTSManager(
        {
            "edge_tts": FakeProvider("edge_tts", should_fail=True),
            "piper": FakeProvider("piper", should_fail=True),
            "gtts": FakeProvider("gtts", should_fail=True),
            "silent": FakeProvider("silent"),
        }
    )

    result = manager.generate_voice("Xin chao", str(tmp_path / "voice.wav"), TTSSettings())

    assert result.provider == "silent"
    assert result.fallback_used is True
    assert result.duration == 1.25
