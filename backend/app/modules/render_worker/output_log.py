from __future__ import annotations

from time import perf_counter
from typing import Any, Callable


def base_name(index: int, preview_only: bool) -> str:
    return f"preview_{index:03d}" if preview_only else f"video_{index:03d}"


def run_step(output_log: dict[str, Any], name: str, action: Callable[[], Any]) -> Any:
    start = perf_counter()
    try:
        result = action()
    except Exception as exc:
        elapsed = round(perf_counter() - start, 3)
        _record_performance(output_log, name, elapsed)
        message = detail_message(str(exc))
        output_log["steps"].append(
            {
                "name": name,
                "status": "failed",
                "message": message,
                "duration_seconds": elapsed,
            }
        )
        raise RuntimeError(f"{name} failed: {message}") from exc

    elapsed = round(perf_counter() - start, 3)
    _record_performance(output_log, name, elapsed)
    output_log["steps"].append(
        {
            "name": name,
            "status": "success",
            "message": "",
            "duration_seconds": elapsed,
        }
    )
    return result


def status_from_log(output_log: dict[str, Any]) -> str:
    if output_log.get("errors"):
        return "failed"
    if output_log.get("warnings"):
        return "warning"
    return "success"


def extend_warnings(output_log: dict[str, Any], warnings: list[str] | tuple[str, ...]) -> None:
    for warning in warnings:
        if warning and warning not in output_log["warnings"]:
            output_log["warnings"].append(str(warning))


def extend_errors(output_log: dict[str, Any], errors: list[str] | tuple[str, ...]) -> None:
    for error in errors:
        if error and error not in output_log["errors"]:
            output_log["errors"].append(str(error))


def short_messages(messages: list[str]) -> list[str]:
    shortened: list[str] = []
    seen: set[str] = set()
    for message in messages:
        item = short_message(message)
        if item and item not in seen:
            seen.add(item)
            shortened.append(item)
    return shortened


def short_message(message: str, limit: int = 360) -> str:
    cleaned = " ".join(str(message).split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def detail_message(message: str, limit: int = 5000) -> str:
    cleaned = str(message).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def _record_performance(output_log: dict[str, Any], step_name: str, elapsed: float) -> None:
    key_map = {
        "render_visual": "render_visual_seconds",
        "generate_script": "script_seconds",
        "generate_voice": "tts_seconds",
        "normalize_voice": "normalize_voice_seconds",
        "generate_subtitle": "subtitle_seconds",
        "select_music": "select_music_seconds",
        "render_final": "render_final_seconds",
        "qa_check": "qa_seconds",
        "write_timeline_report": "timeline_seconds",
    }
    performance = output_log.setdefault("performance", {})
    if not isinstance(performance, dict):
        performance = {}
        output_log["performance"] = performance
    key = key_map.get(step_name, f"{step_name}_seconds")
    performance[key] = round(float(performance.get(key, 0.0)) + elapsed, 3)
