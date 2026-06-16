from __future__ import annotations

from app.modules.tts.tts_schema import TTSSettings


def voiceover_tts_settings(
    base_settings: TTSSettings | None,
    *,
    provider: str,
    voice: str,
    language: str,
    output_format: str = "mp3",
    fallback_provider: str = "piper",
) -> TTSSettings:
    """Merge project-level TTS auth/policy with per-flow voice choices."""

    base = base_settings or TTSSettings()
    return base.model_copy(
        update={
            "provider": provider or base.provider,
            "fallback_provider": base.fallback_provider or fallback_provider,
            "voice": voice or base.voice,
            "language": language or base.language,
            "output_format": output_format or base.output_format,
        }
    )
