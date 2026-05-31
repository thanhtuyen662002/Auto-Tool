from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class EdgeTTSProvider(BaseTTSProvider):
    id = "edge_tts"
    name = "Edge TTS"
    online = True
    recommended = True
    output_format = "mp3"

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        if not text.strip():
            raise TTSProviderError("Edge TTS received empty text.")

        try:
            import edge_tts
        except ImportError as exc:
            raise TTSProviderError("edge-tts is not installed. Run `py -m pip install -r requirements.txt`.") from exc

        target = self._target_path(output_path, "mp3")
        retries = _retry_count()
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            target.unlink(missing_ok=True)
            try:
                asyncio.run(self._generate_async(edge_tts, text, target, settings))
                result = self._success(target)
                if attempt > 1:
                    result.warnings.append(f"Edge TTS đã tạo giọng đọc thành công sau khi thử lại {attempt}/{retries}.")
                return result
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(1.0, 0.25 * attempt))

        # Build friendly error message
        err_str = str(last_error or "unknown error")
        if any(kw in err_str.lower() for kw in ("timeout", "connect", "network", "ssl", "name resolution")):
            friendly = (
                f"Edge TTS không kết nối được sau {retries} lần thử. "
                "Hãy kiểm tra kết nối internet và thử lại."
            )
        else:
            friendly = f"Edge TTS lỗi sau {retries} lần thử: {err_str[:200]}"
        raise TTSProviderError(friendly) from last_error

    async def _generate_async(self, edge_tts_module: object, text: str, output_path: Path, settings: TTSSettings) -> None:
        communicate = edge_tts_module.Communicate(
            text,
            voice=settings.voice or "vi-VN-HoaiMyNeural",
            rate=settings.rate or "+0%",
            volume=settings.volume or "+0%",
            pitch=settings.pitch or "+0Hz",
        )
        await asyncio.wait_for(communicate.save(str(output_path)), timeout=_timeout_seconds())


def _retry_count() -> int:
    raw_value = os.getenv("AUTO_TOOL_TTS_RETRIES", "2")
    try:
        value = int(raw_value)
    except ValueError:
        value = 2
    return max(1, min(5, value))


def _timeout_seconds() -> float:
    raw_value = os.getenv("AUTO_TOOL_TTS_TIMEOUT", "60")
    try:
        return max(5.0, float(raw_value))
    except ValueError:
        return 60.0
