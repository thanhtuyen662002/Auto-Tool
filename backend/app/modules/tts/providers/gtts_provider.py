from __future__ import annotations

from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class GTTSProvider(BaseTTSProvider):
    id = "gtts"
    name = "gTTS"
    online = True
    recommended = False
    output_format = "mp3"

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        if not text.strip():
            raise TTSProviderError("gTTS received empty text.")

        try:
            from gtts import gTTS
        except ImportError as exc:
            raise TTSProviderError("gTTS is not installed. Run `py -m pip install -r requirements.txt`.") from exc

        target = self._target_path(output_path, "mp3")
        language = _language_code(settings.language)
        try:
            gTTS(text=text, lang=language).save(str(target))
        except Exception as exc:
            raise TTSProviderError(f"gTTS failed: {exc}") from exc

        return self._success(target)


def _language_code(language: str) -> str:
    normalized = language.strip().lower()
    if normalized.startswith("vi"):
        return "vi"
    if normalized.startswith("en"):
        return "en"
    return normalized.split("-", 1)[0] or "vi"
