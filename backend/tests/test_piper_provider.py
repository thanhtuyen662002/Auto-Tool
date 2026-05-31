from __future__ import annotations

import pytest

from app.modules.tts.providers.base import TTSProviderError
from app.modules.tts.providers.piper_provider import PiperProvider
from app.modules.tts.tts_schema import TTSSettings


def test_piper_provider_reports_missing_model_path(tmp_path, monkeypatch):
    monkeypatch.delenv("PIPER_MODEL_PATH", raising=False)
    monkeypatch.delenv("PIPER_CONFIG_PATH", raising=False)

    with pytest.raises(TTSProviderError, match="PIPER_MODEL_PATH"):
        PiperProvider().generate("Xin chao", str(tmp_path / "voice.wav"), TTSSettings(provider="piper"))
