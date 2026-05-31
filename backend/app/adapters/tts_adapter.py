from __future__ import annotations

import os
from pathlib import Path

from app.modules.tts.tts_manager import TTSManager
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class TTSAdapter:
    """Compatibility wrapper around TTSManager for older call sites/tests."""

    def __init__(self, manager: TTSManager | None = None) -> None:
        self.manager = manager or TTSManager()
        self.warnings: list[str] = []
        self.last_provider: str | None = None
        self.locked_provider: str | None = None
        self.last_result: TTSResult | None = None

    def lock_provider(self, provider: str | None) -> None:
        self.locked_provider = provider.strip().lower().replace("-", "_") if provider else None
        self.manager.lock_provider(self.locked_provider)

    def generate_voice(self, text: str, output_path: str, language: str | TTSSettings = "vi") -> str:
        if isinstance(language, TTSSettings):
            settings = language
        else:
            settings = TTSSettings(
                provider=os.getenv("AUTO_TOOL_TTS_PROVIDER", "edge_tts"),
                fallback_provider=os.getenv("AUTO_TOOL_TTS_FALLBACK_PROVIDER", "piper"),
                voice=os.getenv("AUTO_TOOL_TTS_VOICE", "vi-VN-HoaiMyNeural"),
                language=language,
                api_key=os.getenv("GOOGLE_TTS_API_KEY") or os.getenv("GOOGLE_CLOUD_TTS_API_KEY"),
                credentials_json_path=(
                    os.getenv("GOOGLE_TTS_CREDENTIALS_JSON_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                ),
                access_token=os.getenv("GOOGLE_TTS_ACCESS_TOKEN"),
                rate=os.getenv("AUTO_TOOL_TTS_RATE", "+0%"),
                pitch=os.getenv("AUTO_TOOL_TTS_PITCH", "+0Hz"),
                volume=os.getenv("AUTO_TOOL_TTS_VOLUME", "+0%"),
                output_format=Path(output_path).suffix.lower().lstrip(".") or os.getenv("AUTO_TOOL_TTS_FORMAT", "mp3"),
            )
        result = self.manager.generate_voice(text, output_path, settings)
        self.warnings = list(result.warnings)
        self.last_provider = result.provider
        self.last_result = result
        return result.output_path
