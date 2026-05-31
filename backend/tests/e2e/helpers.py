from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from app.adapters.ffmpeg_adapter import FFmpegError, MissingFFmpegError, run_ffmpeg
from app.modules.tts.tts_manager import TTSManager
from app.modules.tts.tts_schema import TTSResult, TTSSettings


DONE_STATUSES = {"completed", "completed_with_errors", "failed"}


def write_project_config(
    tmp_path: Path,
    output_count: int = 3,
    duration: float = 4.0,
    source_count: int = 3,
) -> Path:
    source_dir = tmp_path / "sample_videos" / "sample_product"
    output_dir = tmp_path / "outputs"
    create_dummy_videos(source_dir, count=source_count)

    config = {
        "project_name": "e2e-product",
        "source_folder": "./sample_videos/sample_product",
        "output_folder": "./outputs",
        "product": {
            "name": "Sample Product",
            "brand": "Sample Brand",
            "description": "Sample product used for Auto Tool acceptance tests.",
            "features": [
                "Compact design",
                "Easy to use",
                "Useful for daily needs",
            ],
            "cta": "Xem chi tiet san pham ngay",
        },
        "render": {
            "output_count": output_count,
            "duration": duration,
            "aspect_ratio": "9:16",
            "resolution": "180x320",
            "fps": 12,
        },
        "effects": {
            "cut_intensity": 65,
            "speed_variation": 0,
            "grain": 0,
            "zoom_motion": 0,
            "overlay_height": 33,
            "subtitle_size": 24,
        },
        "ai": {
            "text_model": "gemini-test",
            "tone": "friendly_reviewer",
            "language": "vi",
            "gemini_api_keys": [],
        },
        "music": {
            "enabled": False,
            "source_folder": None,
            "source_file": None,
            "volume": 0.12,
            "fade_in": 0.5,
            "fade_out": 0.8,
        },
        "timeline": {
            "template_id": "ugc_reviewer_natural",
        },
        "script_variation": {
            "mode": "auto_mix",
        },
        "tts": {
            "provider": "edge_tts",
            "fallback_provider": "piper",
            "voice": "vi-VN-HoaiMyNeural",
            "language": "vi",
            "api_key": None,
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "output_format": "wav",
        },
    }
    config_path = tmp_path / "product_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    return config_path


def create_dummy_videos(source_dir: Path, count: int = 3, duration: float = 4.6) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        output_path = source_dir / f"source_{index:03d}.mp4"
        if output_path.exists():
            continue
        try:
            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=size=180x320:rate=12:duration={duration:.3f}",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={440 + index * 70}:duration={duration:.3f}",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "28",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "64k",
                    str(output_path),
                ]
            )
        except (MissingFFmpegError, FFmpegError) as exc:
            pytest.skip(f"FFmpeg is required for E2E media tests: {exc}")


def patch_fast_tts(monkeypatch: pytest.MonkeyPatch, fail_pattern: str | None = None) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    monkeypatch.setenv("AUTO_TOOL_TTS_PROVIDER", "edge_tts")

    def fake_generate_voice(self: TTSManager, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        target = Path(output_path)
        if fail_pattern and re.search(fail_pattern, str(target)):
            raise RuntimeError("TTS failed during acceptance test")
        target.parent.mkdir(parents=True, exist_ok=True)
        args = [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=0.450",
            "-ac",
            "1",
            "-ar",
            "44100",
        ]
        if target.suffix.lower() == ".mp3":
            args.extend(["-c:a", "libmp3lame", "-b:a", "96k"])
        else:
            args.extend(["-acodec", "pcm_s16le"])
        args.append(str(target))
        run_ffmpeg(args)
        self.warnings = []
        self.last_provider = "edge_tts"
        result = TTSResult(
            provider="edge_tts",
            output_path=str(target),
            duration=0.45,
            format=target.suffix.lower().lstrip(".") or "wav",
            success=True,
        )
        self.last_result = result
        return result

    monkeypatch.setattr(TTSManager, "generate_voice", fake_generate_voice)


def wait_for_job(client: Any, job_id: str, timeout_seconds: float = 90.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] | None = None
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] in DONE_STATUSES:
            return last_payload
        time.sleep(0.25)
    raise AssertionError(f"Job {job_id} did not finish in time. Last payload: {last_payload}")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_no_placeholder(value: Any) -> None:
    placeholders: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, str):
            placeholders.update(re.findall(r"\{[a-zA-Z0-9_]+\}", item))
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)

    walk(value)
    assert placeholders == set()


def assert_no_raw_traceback(payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    assert "Traceback (most recent call last)" not in text
    assert "File \"" not in text


def source_run_lengths(timeline_payload: dict[str, Any]) -> list[int]:
    runs: list[int] = []
    current_source = None
    current_count = 0
    for clip in timeline_payload.get("clips", []):
        source = clip.get("source_path")
        if source == current_source:
            current_count += 1
        else:
            if current_count:
                runs.append(current_count)
            current_source = source
            current_count = 1
    if current_count:
        runs.append(current_count)
    return runs
