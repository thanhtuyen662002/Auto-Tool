from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import run_ffmpeg
from app.modules.tts.providers.base import BaseTTSProvider
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class SilentProvider(BaseTTSProvider):
    id = "silent"
    name = "Âm thanh im lặng"
    online = False
    recommended = False
    output_format = "wav"

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        extension = "mp3" if settings.output_format == "mp3" else "wav"
        target = self._target_path(output_path, extension)
        duration = max(3.0, len(text) / 12.0)
        args = [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=44100",
            "-t",
            f"{duration:.3f}",
        ]
        if extension == "mp3":
            args.extend(["-c:a", "libmp3lame", "-b:a", "96k"])
        else:
            args.extend(["-acodec", "pcm_s16le"])
        args.append(str(target))
        run_ffmpeg(args)
        result = self._success(Path(target), warnings=["silent_tts_fallback: TTS đã dùng âm thanh im lặng để tránh làm hỏng batch render."])
        result.duration = round(duration, 3)
        return result
