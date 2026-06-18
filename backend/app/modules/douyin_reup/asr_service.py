from __future__ import annotations

import threading
import os
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import probe_video, run_ffmpeg
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, write_srt_blocks
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ASRService:
    _model_cache_lock = threading.Lock()
    _model_cache: dict[tuple[str, str], tuple[Any, threading.Lock]] = {}

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def transcribe_to_srt(
        self,
        video_path: str,
        output_srt_path: str,
        language: str = "zh",
        provider: str = "faster_whisper",
        model_size: str = "medium",
        device: str = "auto",
        vad_filter: bool = False,
        max_audio_seconds: int | float | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        self.warnings = []
        if provider.strip().lower() != "faster_whisper":
            raise RuntimeError(f"ASR provider chưa được hỗ trợ: {provider}")

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Chưa cài faster-whisper nên không thể tự nhận diện giọng nói. "
                "Hãy chạy `py -m pip install -r backend/requirements.txt`, dùng bản exe mới đã bundle ASR, "
                "hoặc đặt file .srt đi kèm video."
            ) from exc

        target = Path(output_srt_path)
        ensure_dir(target.parent)
        audio_path = target.with_name(f"{target.stem}_asr_audio.wav")
        audio_limit = _asr_audio_limit_seconds(video_path, max_audio_seconds=max_audio_seconds)
        trim_args = ["-t", f"{audio_limit:.3f}"] if audio_limit else []
        _progress(progress_callback, "asr_extracting_audio", 10)
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(Path(video_path).expanduser().resolve()),
                *trim_args,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio_path),
            ]
        )

        model_device = device.strip().lower()
        if model_device not in {"auto", "cpu", "cuda"}:
            model_device = "auto"
        normalized_size = model_size.strip() or "medium"
        _progress(progress_callback, "asr_loading_model", 20)
        cache_key = (normalized_size, model_device)
        with self._model_cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is None:
                cached = (
                    WhisperModel(normalized_size, device=model_device, compute_type="int8"),
                    threading.Lock(),
                )
                self._model_cache[cache_key] = cached
        model, inference_lock = cached
        _progress(progress_callback, "asr_transcribing", 35)
        language_code = language.strip() or None
        with inference_lock:
            segments = self._transcribe_with_vad_fallback(
                model=model,
                audio_path=str(audio_path),
                language=language_code,
                vad_filter=vad_filter,
            )
            blocks = self._segments_to_blocks(segments)
            if not blocks and vad_filter:
                warning = (
                    "ASR bật VAD nhưng không nhận diện được câu nào; đã thử lại không dùng VAD "
                    "để tránh bỏ sót thoại nhanh hoặc nền âm ồn."
                )
                logger.warning(warning)
                self.warnings.append(warning)
                segments = self._transcribe_segments(
                    model,
                    str(audio_path),
                    language_code,
                    vad_filter=False,
                )
                blocks = self._segments_to_blocks(segments)

        if not blocks:
            raise RuntimeError(f"ASR không nhận diện được subtitle từ video: {video_path}")
        _progress(progress_callback, "asr_writing_subtitles", 95)
        result = write_srt_blocks(blocks, str(target))
        _progress(progress_callback, "asr_completed", 100)
        return result

    def _transcribe_with_vad_fallback(
        self,
        model: Any,
        audio_path: str,
        language: str | None,
        vad_filter: bool = False,
    ) -> list[Any]:
        try:
            return self._transcribe_segments(model, audio_path, language, vad_filter=vad_filter)
        except Exception as exc:
            if not vad_filter or not _is_missing_vad_asset_error(exc):
                raise
            warning = (
                "Không tìm thấy asset Silero VAD của faster-whisper trong runtime. "
                "ASR đã thử lại không dùng VAD để tránh fail video."
            )
            logger.warning("%s Chi tiết: %s", warning, exc)
            self.warnings.append(warning)
            return self._transcribe_segments(model, audio_path, language, vad_filter=False)

    def _transcribe_segments(
        self,
        model: Any,
        audio_path: str,
        language: str | None,
        vad_filter: bool,
    ) -> list[Any]:
        segments, _info = model.transcribe(
            audio_path,
            language=language,
            vad_filter=vad_filter,
            beam_size=5,
            best_of=5,
            condition_on_previous_text=True,
        )
        return list(segments)

    @staticmethod
    def _segments_to_blocks(segments: list[Any]) -> list[SubtitleBlock]:
        blocks: list[SubtitleBlock] = []
        for segment in segments:
            text = " ".join(str(segment.text or "").split())
            if not text:
                continue
            start = max(0.0, float(segment.start))
            end = max(start + 0.1, float(segment.end))
            blocks.append(
                SubtitleBlock(
                    index=len(blocks) + 1,
                    start=start,
                    end=end,
                    text=text,
                )
            )
        return blocks


def _asr_audio_limit_seconds(video_path: str, max_audio_seconds: int | float | None = None) -> float | None:
    if max_audio_seconds is None:
        raw = os.getenv("AUTO_TOOL_ASR_MAX_AUDIO_SECONDS", "180").strip()
        try:
            limit = float(raw)
        except ValueError:
            limit = 180.0
    else:
        try:
            limit = float(max_audio_seconds)
        except (TypeError, ValueError):
            limit = 180.0
    if limit <= 0:
        return None
    try:
        duration = probe_video(video_path).duration
    except Exception:
        return limit
    return min(max(1.0, duration), limit)


def _is_missing_vad_asset_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "silero_vad" in message
        or ("vad" in message and "no_suchfile" in message)
        or ("vad" in message and "file doesn't exist" in message)
        or ("vad" in message and "file does not exist" in message)
    )


def _progress(
    callback: Callable[[dict[str, Any]], None] | None,
    step: str,
    progress: int,
) -> None:
    if callback:
        callback({"current_step": step, "progress": max(0, min(100, int(progress)))})
