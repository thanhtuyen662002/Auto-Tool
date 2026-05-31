from __future__ import annotations

from app.modules.tts.providers import EdgeTTSProvider, GoogleCloudTTSProvider, GTTSProvider, PiperProvider, SilentProvider
from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_schema import TTSProviderInfo, TTSResult, TTSSettings
from app.utils.logger import get_logger


logger = get_logger(__name__)


class TTSManager:
    def __init__(self, providers: dict[str, BaseTTSProvider] | None = None) -> None:
        self.providers = providers or _default_providers()
        self.warnings: list[str] = []
        self.last_provider: str | None = None
        self.locked_provider: str | None = None
        self.last_result: TTSResult | None = None

    def lock_provider(self, provider: str | None) -> None:
        self.locked_provider = _normalize_provider_id(provider) if provider else None

    def generate_voice(self, text: str, output_path: str, settings: TTSSettings | None = None) -> TTSResult:
        settings = settings or TTSSettings()
        self.warnings = []
        self.last_provider = None
        self.last_result = None
        provider_order = self._provider_order(settings)

        for index, provider_id in enumerate(provider_order):
            provider = self.providers.get(provider_id)
            if provider is None:
                warning = f"Nhà cung cấp TTS chưa được đăng ký: {provider_id}"
                self._warn(warning)
                continue

            try:
                result = provider.generate(text, output_path, settings)
                result.fallback_used = index > 0 or provider_id != _normalize_provider_id(settings.provider)
                result.warnings = [*self.warnings, *result.warnings]
                self.warnings = result.warnings
                self.last_provider = result.provider
                self.last_result = result
                return result
            except Exception as exc:
                message = f"{provider.name} lỗi: {exc}"
                self._warn(message)

        raise TTSProviderError("Tất cả nhà cung cấp TTS đều lỗi.")

    def _provider_order(self, settings: TTSSettings) -> list[str]:
        if self.locked_provider:
            requested = [self.locked_provider]
        else:
            requested = [
                _normalize_provider_id(settings.provider),
                _normalize_provider_id(settings.fallback_provider),
                "gtts",
            ]
        requested.append("silent")

        ordered: list[str] = []
        for item in requested:
            if item and item not in ordered:
                ordered.append(item)
        return ordered

    def _warn(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)


def list_tts_providers() -> list[TTSProviderInfo]:
    providers = _default_providers()
    return [
        providers["edge_tts"].info(),
        providers["google_cloud_tts"].info(),
        providers["piper"].info(),
        providers["gtts"].info(),
        providers["silent"].info(),
    ]


def _default_providers() -> dict[str, BaseTTSProvider]:
    return {
        "edge_tts": EdgeTTSProvider(),
        "google_cloud_tts": GoogleCloudTTSProvider(),
        "piper": PiperProvider(),
        "gtts": GTTSProvider(),
        "silent": SilentProvider(),
    }


def _normalize_provider_id(provider: str | None) -> str:
    value = (provider or "").strip().lower().replace("-", "_")
    aliases = {
        "edge": "edge_tts",
        "edge_tts": "edge_tts",
        "google_cloud": "google_cloud_tts",
        "google_cloud_tts": "google_cloud_tts",
        "google_cloud_text_to_speech": "google_cloud_tts",
        "piper_offline": "piper",
        "google": "gtts",
        "google_tts": "gtts",
        "google_translate": "gtts",
        "mock": "silent",
        "none": "silent",
    }
    return aliases.get(value, value)
