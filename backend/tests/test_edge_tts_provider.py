from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from app.modules.tts.providers.edge_tts_provider import EdgeTTSProvider
from app.modules.tts.tts_schema import TTSResult, TTSSettings


def test_edge_tts_provider_retries_and_returns_duration(tmp_path, monkeypatch):
    calls: list[int] = []

    class FakeCommunicate:
        def __init__(self, text: str, voice: str, rate: str, volume: str, pitch: str) -> None:
            self.text = text
            self.voice = voice

        async def save(self, output_path: str) -> None:
            calls.append(len(calls) + 1)
            if len(calls) == 1:
                raise RuntimeError("temporary edge failure")
            Path(output_path).write_bytes(b"mp3")

    def fake_success(self: EdgeTTSProvider, output_path: Path, warnings=None) -> TTSResult:
        return TTSResult(
            provider="edge_tts",
            output_path=str(output_path),
            duration=1.5,
            format="mp3",
            success=True,
            warnings=warnings or [],
        )

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=FakeCommunicate))
    monkeypatch.setenv("AUTO_TOOL_TTS_RETRIES", "2")
    monkeypatch.setattr(EdgeTTSProvider, "_success", fake_success)

    result = EdgeTTSProvider().generate("Xin chao", str(tmp_path / "voice.wav"), TTSSettings())

    assert calls == [1, 2]
    assert result.provider == "edge_tts"
    assert result.duration == 1.5
    assert result.output_path.endswith(".mp3")
    assert any("thử lại 2/2" in warning for warning in result.warnings)
