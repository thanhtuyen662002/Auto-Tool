from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class PiperProvider(BaseTTSProvider):
    id = "piper"
    name = "Piper Offline TTS"
    online = False
    recommended = False
    output_format = "wav"

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        if not text.strip():
            raise TTSProviderError("Piper received empty text.")

        model_path = os.getenv("PIPER_MODEL_PATH", "").strip()
        config_path = os.getenv("PIPER_CONFIG_PATH", "").strip()
        if not model_path:
            raise TTSProviderError("PIPER_MODEL_PATH is not configured.")
        if not config_path:
            raise TTSProviderError("PIPER_CONFIG_PATH is not configured.")
        if not Path(model_path).exists():
            raise TTSProviderError(f"Piper model file does not exist: {model_path}")
        if not Path(config_path).exists():
            raise TTSProviderError(f"Piper config file does not exist: {config_path}")

        executable = shutil.which("piper")
        if not executable:
            raise TTSProviderError("Piper executable was not found in PATH.")

        target = self._target_path(output_path, "wav")
        command = [
            executable,
            "--model",
            model_path,
            "--config",
            config_path,
            "--output_file",
            str(target),
        ]
        try:
            result = subprocess.run(
                command,
                input=text,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TTSProviderError(f"Piper failed to start: {exc}") from exc

        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip() or "No Piper output was captured."
            raise TTSProviderError(f"Piper failed: {details}")

        return self._success(target)
