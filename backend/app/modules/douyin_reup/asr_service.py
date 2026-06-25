from __future__ import annotations

import threading
import os
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import probe_video, run_ffmpeg
from app.modules.douyin_reup.subtitle_quality_gate import segment_is_low_quality
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, write_srt_blocks
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)

# ─── GPU availability cache ───────────────────────────────────────────────────
# Khi GPU/CUDA lần đầu fail (lỗi phần cứng), cache ngay kết quả để hàng nghìn
# video sau dùng CPU trực tiếp — không mất thời gian thử GPU rồi fail lại.
_GPU_AVAILABLE: bool | None = None  # None = chưa kiểm tra, True/False = đã biết
_GPU_CACHE_LOCK = threading.Lock()


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

        # Xác định device: nếu GPU đã fail trước đó trong session này thì dùng CPU ngay
        model_device = _resolve_asr_device(device)
        normalized_size = model_size.strip() or "medium"
        _progress(progress_callback, "asr_loading_model", 20)
        model, inference_lock = self._get_or_load_model(WhisperModel, normalized_size, model_device)
        _progress(progress_callback, "asr_transcribing", 35)
        language_code = language.strip() or None
        try:
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
        except Exception as exc:
            if _is_asr_hardware_error(exc) and model_device != "cpu":
                # GPU fail → đánh dấu không dùng GPU nữa trong session này
                # để hàng nghìn video sau dùng CPU ngay, không thử lại GPU
                _mark_gpu_unavailable()
                warning = (
                    f"ASR GPU/CUDA không khả dụng ({_short_hardware_error(exc)}); "
                    "tự động chuyển sang CPU để tiếp tục xử lý batch."
                )
                logger.warning(warning)
                self.warnings.append(warning)
                _progress(progress_callback, "asr_loading_model_cpu", 22)
                cpu_model, cpu_lock = self._get_or_load_model(WhisperModel, normalized_size, "cpu")
                with cpu_lock:
                    segments = self._transcribe_with_vad_fallback(
                        model=cpu_model,
                        audio_path=str(audio_path),
                        language=language_code,
                        vad_filter=vad_filter,
                    )
                    blocks = self._segments_to_blocks(segments)
                    if not blocks and vad_filter:
                        segments = self._transcribe_segments(
                            cpu_model, str(audio_path), language_code, vad_filter=False
                        )
                        blocks = self._segments_to_blocks(segments)
            else:
                raise

        if not blocks:
            raise RuntimeError(f"ASR không nhận diện được subtitle từ video: {video_path}")
        _progress(progress_callback, "asr_writing_subtitles", 95)
        result = write_srt_blocks(blocks, str(target))
        _progress(progress_callback, "asr_completed", 100)
        return result

    def _get_or_load_model(self, WhisperModel: Any, model_size: str, device: str) -> tuple[Any, threading.Lock]:
        cache_key = (model_size, device)
        with self._model_cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is None:
                cached = (
                    WhisperModel(model_size, device=device, compute_type="int8"),
                    threading.Lock(),
                )
                self._model_cache[cache_key] = cached
        return cached

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
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
        )
        return list(segments)

    def _segments_to_blocks(self, segments: list[Any]) -> list[SubtitleBlock]:
        blocks: list[SubtitleBlock] = []
        for segment in segments:
            text = " ".join(str(segment.text or "").split())
            is_low_quality, reasons = segment_is_low_quality(
                text,
                no_speech_prob=_float_attr(segment, "no_speech_prob"),
                avg_logprob=_float_attr(segment, "avg_logprob"),
                compression_ratio=_float_attr(segment, "compression_ratio"),
            )
            if is_low_quality:
                self.warnings.append(f"ASR bỏ qua một đoạn nghi nhiễu: {', '.join(reasons)}")
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


def _is_asr_hardware_error(exc: Exception) -> bool:
    """Nhận diện lỗi phần cứng GPU/CUDA (cublas, cuDNN, CUDA runtime thiếu).
    Phân biệt với lỗi logic như 'video không có thoại'.
    """
    message = str(exc).lower()
    hardware_keywords = (
        "cublas",
        "cudnn",
        "cuda",
        "libcuda",
        "nvcuda",
        "curand",
        "cannot be loaded",
        "not found or cannot",
        "failed to load",
        "no cuda",
        "gpu",
        "device unavailable",
    )
    return any(kw in message for kw in hardware_keywords)


def _short_hardware_error(exc: Exception) -> str:
    """Rút ngắn thông báo lỗi GPU cho log dễ đọc."""
    text = str(exc).split("\n")[0].strip()
    return text[:120] if len(text) > 120 else text


def _resolve_asr_device(requested_device: str) -> str:
    """Xác định device thực tế sẽ dùng.
    - Nếu GPU đã được biết là không khả dụng trong session này → dùng CPU ngay.
    - Nếu user chỉ định CPU rõ ràng → giữ CPU.
    - Còn lại → dùng device được yêu cầu (auto/cuda).
    """
    device = (requested_device or "auto").strip().lower()
    if device not in {"auto", "cpu", "cuda"}:
        device = "auto"
    if device == "cpu":
        return "cpu"
    # Kiểm tra cache GPU
    with _GPU_CACHE_LOCK:
        if _GPU_AVAILABLE is False:
            return "cpu"
    return device


def _mark_gpu_unavailable() -> None:
    """Đánh dấu GPU không khả dụng để các video sau trong batch dùng CPU ngay."""
    global _GPU_AVAILABLE  # noqa: PLW0603
    with _GPU_CACHE_LOCK:
        _GPU_AVAILABLE = False
    logger.info("ASR: GPU/CUDA không khả dụng — toàn bộ video còn lại trong batch sẽ dùng CPU.")


def is_asr_gpu_available() -> bool:
    """Kiểm tra GPU sẵn sàng cho ASR (có thể gọi từ UI để cảnh báo user).
    Trả về False nếu đã biết GPU fail trong session này.
    """
    with _GPU_CACHE_LOCK:
        if _GPU_AVAILABLE is False:
            return False
    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415
        _ = WhisperModel("tiny", device="cuda", compute_type="int8")
        with _GPU_CACHE_LOCK:
            global _GPU_AVAILABLE  # noqa: PLW0603
            _GPU_AVAILABLE = True
        return True
    except Exception:
        _mark_gpu_unavailable()
        return False


def _float_attr(segment: Any, name: str) -> float | None:
    value = getattr(segment, name, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _progress(
    callback: Callable[[dict[str, Any]], None] | None,
    step: str,
    progress: int,
) -> None:
    if callback:
        callback({"current_step": step, "progress": max(0, min(100, int(progress)))})
