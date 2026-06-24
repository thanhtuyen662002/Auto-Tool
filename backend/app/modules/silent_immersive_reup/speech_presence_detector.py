from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_video
from app.modules.douyin_reup.subtitle_timing_guard import clean_subtitle_text, parse_srt_blocks
from app.modules.silent_immersive_reup.silent_schema import SpeechPresenceResult
from app.utils.dependency_manager import DependencyError, resolve_tool
from app.utils.process_isolation import run_in_isolated_process
from app.utils.subprocess_utils import run_hidden


class SpeechPresenceDetector:
    def __init__(self, threshold: float = 0.35, enable_asr: bool | None = None) -> None:
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.enable_asr = enable_asr

    def detect(self, video_path: str) -> SpeechPresenceResult:
        warnings: list[str] = []
        try:
            media = probe_video(video_path)
        except Exception as exc:
            return SpeechPresenceResult(
                video_path=video_path,
                has_speech=False,
                speech_score=0.0,
                audio_energy_score=None,
                speech_segments_count=0,
                method="ffprobe_failed",
                warnings=[f"Không đọc được metadata audio để detect speech: {exc}"],
            )

        if not media.has_audio:
            return SpeechPresenceResult(
                video_path=video_path,
                has_speech=False,
                speech_score=0.0,
                audio_energy_score=0.0,
                speech_segments_count=0,
                method="no_audio",
                warnings=[],
            )

        energy_score = self._audio_energy_score(video_path, max_duration=min(media.duration, 20.0), warnings=warnings)
        speech_score = min(0.34, energy_score * 0.34)
        speech_segments_count = 0
        method = "audio_energy_heuristic"

        if self._should_run_asr(energy_score):
            try:
                speech_segments_count = self._asr_segment_count(video_path)
                asr_score = min(1.0, speech_segments_count / 4.0)
                speech_score = asr_score
                method = "asr_fast_detect"
            except Exception as exc:
                speech_score = 0.0
                method = "asr_unavailable"
                warnings.append(f"ASR speech detect failed, keep video in silent mode to avoid mistaking music or operation sounds for speech: {exc}")

        if method == "audio_energy_heuristic":
            speech_score = 0.0
            warnings.append(
                "Only audio energy was available, so this is not treated as confirmed speech. The video stays in silent mode unless ASR confirms speech."
            )

        return SpeechPresenceResult(
            video_path=video_path,
            has_speech=speech_score >= self.threshold,
            speech_score=round(speech_score, 4),
            audio_energy_score=round(energy_score, 4),
            speech_segments_count=speech_segments_count,
            method=method,
            warnings=_dedupe(warnings),
        )

    def _should_run_asr(self, energy_score: float = 1.0) -> bool:
        if self.enable_asr is not None:
            return self.enable_asr
        configured = os.getenv("AUTO_TOOL_SILENT_SPEECH_ASR", "").strip().lower()
        if configured in {"0", "false", "no", "off"}:
            return False
        if configured in {"1", "true", "yes", "on"}:
            return True
        if configured and configured != "auto":
            return False
        return energy_score >= _env_float("AUTO_TOOL_SILENT_SPEECH_ASR_MIN_ENERGY", 0.18)

    @staticmethod
    def _audio_energy_score(video_path: str, max_duration: float, warnings: list[str]) -> float:
        try:
            ffmpeg = resolve_tool("ffmpeg")
        except DependencyError as exc:
            warnings.append(str(exc))
            return 0.0

        command = [
            ffmpeg,
            "-hide_banner",
            "-t",
            f"{max_duration:.3f}",
            "-i",
            str(Path(video_path).expanduser().resolve()),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "NUL" if os.name == "nt" else "/dev/null",
        ]
        try:
            result = run_hidden(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            warnings.append("FFmpeg audio-energy check timed out after 120 seconds.")
            return 0.0
        output = "\n".join([result.stdout or "", result.stderr or ""])
        if result.returncode != 0:
            warnings.append("FFmpeg không đo được audio energy cho video.")
            return 0.0

        match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", output)
        if not match:
            return 0.0
        mean_db = float(match.group(1))
        return max(0.0, min(1.0, (mean_db + 55.0) / 35.0))

    @staticmethod
    def _asr_segment_count(video_path: str) -> int:
        if os.getenv("AUTO_TOOL_SILENT_SPEECH_ASR_ISOLATION", "1").strip().lower() not in {"0", "false", "no", "off"}:
            timeout_seconds = _env_int("AUTO_TOOL_SILENT_SPEECH_TIMEOUT_SECONDS", 300)
            return int(
                run_in_isolated_process(
                    _speech_asr_worker,
                    video_path,
                    timeout_seconds=timeout_seconds,
                    stage_name=f"ASR speech detect {Path(video_path).name}",
                )
            )
        return _speech_asr_worker(video_path)


def _speech_asr_worker(video_path: str) -> int:
    from app.modules.douyin_reup.asr_service import ASRService

    with tempfile.TemporaryDirectory(prefix="autotool_speech_detect_") as temp_dir:
        output_path = Path(temp_dir) / "speech_detect.srt"
        ASRService().transcribe_to_srt(
            video_path,
            str(output_path),
            language="zh",
            provider="faster_whisper",
            model_size=os.getenv("AUTO_TOOL_SILENT_SPEECH_MODEL", "tiny"),
            device=os.getenv("AUTO_TOOL_SILENT_SPEECH_DEVICE", "auto"),
            vad_filter=True,
            max_audio_seconds=_env_int("AUTO_TOOL_SILENT_SPEECH_MAX_AUDIO_SECONDS", 30),
        )
        try:
            return _count_reliable_asr_speech_segments(str(output_path))
        except (OSError, FFmpegError):
            return 0


ASR_CREDIT_OR_WATERMARK_RE = re.compile(
    r"("
    r"字幕\s*(?:by|由|[:：])|"
    r"(?:subtitle|subtitles|caption|captions)\s*(?:by|from|created|provided|edited)|"
    r"(?:剪映|capcut)\s*(?:出品|制作|模板|水印)?|"
    r"(?:抖音|douyin|tiktok)\s*(?:号|id|水印|作者|user|@)|"
    r"(?:小米同学)|"
    r"(?:索兰娅|soranya)"
    r")",
    re.IGNORECASE,
)


def _count_reliable_asr_speech_segments(srt_path: str) -> int:
    blocks = parse_srt_blocks(srt_path)
    reliable_blocks = []
    for block in blocks:
        text = clean_subtitle_text(block.text)
        if not text or _is_asr_credit_or_watermark(text):
            continue
        signal_chars = _speech_signal_char_count(text)
        duration = max(0.0, block.end - block.start)
        if signal_chars < 4 and duration < 1.2:
            continue
        reliable_blocks.append((signal_chars, duration))

    if not reliable_blocks:
        return 0
    if len(reliable_blocks) == 1:
        signal_chars, duration = reliable_blocks[0]
        return 2 if signal_chars >= 18 or duration >= 4.0 else 0
    return len(reliable_blocks)


def _is_asr_credit_or_watermark(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text).casefold()
    if not normalized:
        return True
    if ASR_CREDIT_OR_WATERMARK_RE.search(normalized):
        return True
    if normalized.startswith("@") and _speech_signal_char_count(normalized) <= 24:
        return True
    return False


def _speech_signal_char_count(text: str) -> int:
    return len(re.findall(r"[\w\u4e00-\u9fff]", text, flags=re.UNICODE))


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default)).strip()))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(os.getenv(name, str(default)).strip())))
    except ValueError:
        return default


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
