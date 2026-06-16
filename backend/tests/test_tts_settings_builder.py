from __future__ import annotations

from app.modules.tts.settings_builder import voiceover_tts_settings
from app.modules.tts.tts_schema import TTSSettings


def test_voiceover_tts_settings_keeps_project_auth_and_policy() -> None:
    base = TTSSettings(
        provider="edge_tts",
        fallback_provider="piper",
        allow_provider_fallback=False,
        allow_silent_fallback=False,
        voice="vi-VN-HoaiMyNeural",
        api_key="google-key",
        credentials_json_path="D:/keys/service-account.json",
        access_token="token",
    )

    result = voiceover_tts_settings(
        base,
        provider="google_cloud_tts",
        voice="vi-VN-Wavenet-A",
        language="vi",
        output_format="mp3",
    )

    assert result.provider == "google_cloud_tts"
    assert result.voice == "vi-VN-Wavenet-A"
    assert result.api_key == "google-key"
    assert result.credentials_json_path == "D:/keys/service-account.json"
    assert result.access_token == "token"
    assert result.allow_provider_fallback is False
    assert result.allow_silent_fallback is False
