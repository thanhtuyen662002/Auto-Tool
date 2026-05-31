from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_media_duration
from app.modules.tts.tts_schema import TTSProviderInfo, TTSResult, TTSSettings


class TTSProviderError(RuntimeError):
    """Raised when a TTS provider cannot generate audio."""


class BaseTTSProvider(ABC):
    id: str
    name: str
    online: bool
    recommended: bool = False
    requires_api_key: bool = False
    output_format: str = "wav"

    @abstractmethod
    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        """Generate speech for text into output_path."""

    def info(self) -> TTSProviderInfo:
        return TTSProviderInfo(
            id=self.id,
            name=self.name,
            requires_api_key=self.requires_api_key,
            online=self.online,
            recommended=self.recommended,
        )

    def _success(self, output_path: Path, warnings: list[str] | None = None) -> TTSResult:
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise TTSProviderError(f"{self.name} did not create a valid audio file: {output_path}")
        try:
            duration = probe_media_duration(str(output_path))
        except Exception as exc:
            raise TTSProviderError(f"{self.name} created audio but ffprobe could not read duration: {exc}") from exc
        return TTSResult(
            provider=self.id,
            output_path=str(output_path),
            duration=round(duration, 3),
            format=output_path.suffix.lower().lstrip(".") or self.output_format,
            success=True,
            warnings=warnings or [],
        )

    @staticmethod
    def _target_path(output_path: str, extension: str) -> Path:
        target = Path(output_path).expanduser().resolve()
        extension = extension.strip().lower().lstrip(".") or "wav"
        if target.suffix.lower() != f".{extension}":
            target = target.with_suffix(f".{extension}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        return target
