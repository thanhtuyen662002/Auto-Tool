from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.tts.text_cleanup import clean_text_for_tts
from app.modules.tts.tts_manager import TTSManager
from app.modules.tts.tts_schema import TTSSettings
from app.utils.dependency_manager import ensure_runtime_dependencies
from app.utils.env_loader import load_local_env


def main() -> int:
    load_local_env()
    args = _parse_args()
    ensure_runtime_dependencies(auto_install=None, include_piper=args.provider == "piper")

    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_format = output_path.suffix.lower().lstrip(".") or "mp3"
    text = clean_text_for_tts(args.text)

    settings = TTSSettings(
        provider=args.provider,
        fallback_provider=args.fallback_provider,
        voice=args.voice,
        language=args.language,
        api_key=args.api_key,
        credentials_json_path=args.credentials_json_path,
        access_token=args.access_token,
        output_format=output_format,
    )
    result = TTSManager().generate_voice(text, str(output_path), settings)
    print(
        json.dumps(
            {
                "provider": result.provider,
                "success": result.success,
                "output_path": result.output_path,
                "duration": result.duration,
                "format": result.format,
                "warnings": result.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a real TTS sample for Auto Tool.")
    providers = ["edge_tts", "google_cloud_tts", "piper", "gtts", "silent"]
    parser.add_argument("--provider", choices=providers, required=True)
    parser.add_argument("--fallback-provider", default="silent", choices=providers)
    parser.add_argument("--voice", default="vi-VN-HoaiMyNeural")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--credentials-json-path", default=None)
    parser.add_argument("--access-token", default=None)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
