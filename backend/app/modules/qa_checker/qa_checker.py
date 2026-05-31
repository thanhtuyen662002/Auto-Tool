from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.script_writer.script_writer import ProductVideoScript


PLACEHOLDER_PATTERN = re.compile(r"\{[a-zA-Z0-9_]+\}")


def check_output_video(
    path: str,
    expected_duration: float,
    expected_resolution: str = "1080x1920",
    subtitle_path: str | None = None,
    script_path: str | None = None,
    allow_missing_audio: bool | None = None,
) -> dict[str, Any]:
    output_path = Path(path)
    expected_width, expected_height = _parse_resolution(expected_resolution)
    allow_audio_warning = _allow_missing_audio_warning() if allow_missing_audio is None else allow_missing_audio
    result: dict[str, Any] = {
        "path": str(output_path),
        "passed": False,
        "checks": {},
        "warnings": [],
        "errors": [],
        "exists": output_path.exists(),
        "size_bytes": 0,
        "probe_ok": False,
        "duration": None,
        "width": None,
        "height": None,
        "has_video_stream": False,
        "has_audio_stream": False,
        "duration_ok": False,
        "resolution_ok": False,
    }

    _check_exists_and_size(output_path, result)
    if result["errors"]:
        result["error"] = result["errors"][0]
        return result

    _check_media_probe(output_path, result)
    if result["errors"]:
        result["error"] = result["errors"][0]
        return result

    _check_duration(result, expected_duration)
    _check_resolution(result, expected_width, expected_height)
    _check_audio(result, allow_audio_warning)
    _check_subtitle_file(subtitle_path, result)
    _check_script_file(script_path, result)

    result["passed"] = not result["errors"]
    result["error"] = result["errors"][0] if result["errors"] else None
    return result


def _check_exists_and_size(output_path: Path, result: dict[str, Any]) -> None:
    if not output_path.exists():
        _error(result, "file_exists", "Final video was not created.")
        return

    _success(result, "file_exists", "Final video exists.")
    result["size_bytes"] = output_path.stat().st_size
    if result["size_bytes"] <= 0:
        _error(result, "file_size", "Final video file is empty.")
        return
    _success(result, "file_size", f"Final video size is {result['size_bytes']} bytes.")


def _check_media_probe(output_path: Path, result: dict[str, Any]) -> None:
    try:
        media = probe_video(str(output_path))
    except Exception as exc:
        _error(result, "ffprobe", f"ffprobe could not read final video: {exc}")
        return

    result.update(
        {
            "probe_ok": True,
            "duration": media.duration,
            "width": media.width,
            "height": media.height,
            "has_video_stream": True,
            "has_audio_stream": media.has_audio,
        }
    )
    _success(result, "ffprobe", "ffprobe read final video successfully.")
    _success(result, "video_stream", "Video stream exists.")


def _check_duration(result: dict[str, Any], expected_duration: float) -> None:
    duration = result.get("duration")
    if duration is None:
        _error(result, "duration", "Could not read final video duration.")
        return

    diff = abs(float(duration) - float(expected_duration))
    result["duration_ok"] = diff <= 1.5
    if diff <= 1.5:
        _success(result, "duration", f"Duration is close to target: {duration:.3f}s.")
    elif diff <= 2.0:
        _warning(
            result,
            "duration",
            f"Duration differs from target by {diff:.3f}s, under the 2s warning threshold.",
        )
    else:
        _error(result, "duration", f"Duration differs from target by {diff:.3f}s.")


def _check_resolution(result: dict[str, Any], expected_width: int, expected_height: int) -> None:
    width = result.get("width")
    height = result.get("height")
    result["resolution_ok"] = width == expected_width and height == expected_height
    if result["resolution_ok"]:
        _success(result, "resolution", f"Resolution is {width}x{height}.")
    else:
        _error(result, "resolution", f"Expected {expected_width}x{expected_height}, got {width}x{height}.")


def _check_audio(result: dict[str, Any], allow_missing_audio: bool) -> None:
    if result.get("has_audio_stream"):
        _success(result, "audio_stream", "Audio stream exists.")
        return

    message = "Final video has no audio stream."
    if allow_missing_audio:
        _warning(result, "audio_stream", f"{message} Allowed because mock/silent TTS mode is active.")
    else:
        _error(result, "audio_stream", message)


def _check_subtitle_file(subtitle_path: str | None, result: dict[str, Any]) -> None:
    if not subtitle_path:
        _error(result, "subtitle_file", "Subtitle file path was not provided.")
        return

    path = Path(subtitle_path)
    if not path.exists() or path.stat().st_size <= 0:
        _error(result, "subtitle_file", f"Subtitle file is missing or empty: {path}")
        return

    _success(result, "subtitle_file", "Subtitle file exists.")
    long_lines = _long_subtitle_lines(path)
    if long_lines:
        preview = "; ".join(long_lines[:3])
        _warning(result, "subtitle_length", f"Some subtitle lines are long: {preview}")
    else:
        _success(result, "subtitle_length", "Subtitle line lengths look reasonable.")


def _check_script_file(script_path: str | None, result: dict[str, Any]) -> None:
    if not script_path:
        _error(result, "script_schema", "Script file path was not provided.")
        return

    path = Path(script_path)
    if not path.exists() or path.stat().st_size <= 0:
        _error(result, "script_schema", f"Script JSON is missing or empty: {path}")
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        script = ProductVideoScript.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        _error(result, "script_schema", f"Script JSON does not match schema: {exc}")
        return

    _success(result, "script_schema", "Script JSON matches schema.")
    placeholders = _find_placeholders(script.model_dump(mode="json"))
    if placeholders:
        _error(result, "script_placeholders", f"Script contains unresolved placeholders: {', '.join(placeholders)}")
    else:
        _success(result, "script_placeholders", "Script contains no unresolved placeholders.")


def _long_subtitle_lines(path: Path, max_chars: int = 72) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    long_lines: list[str] = []
    for line in lines:
        text = line.strip()
        if not text or text.isdigit() or "-->" in text:
            continue
        if len(text) > max_chars:
            long_lines.append(text[:120])
    return long_lines


def _find_placeholders(value: Any) -> list[str]:
    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, str):
            found.update(PLACEHOLDER_PATTERN.findall(item))
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)

    walk(value)
    return sorted(found)


def _parse_resolution(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid expected resolution: {value}") from exc


def _allow_missing_audio_warning() -> bool:
    provider = os.getenv("AUTO_TOOL_TTS_PROVIDER", "").strip().lower()
    return provider in {"silent", "mock", "none"}


def _success(result: dict[str, Any], name: str, message: str) -> None:
    result["checks"][name] = {"status": "success", "message": message}


def _warning(result: dict[str, Any], name: str, message: str) -> None:
    result["checks"][name] = {"status": "warning", "message": message}
    result["warnings"].append(message)


def _error(result: dict[str, Any], name: str, message: str) -> None:
    result["checks"][name] = {"status": "failed", "message": message}
    result["errors"].append(message)
