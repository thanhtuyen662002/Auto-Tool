from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.ffmpeg_adapter import run_ffmpeg
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, write_srt_blocks
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ASRService:
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
        run_ffmpeg(
            [
                "-y",
                "-i",
                str(Path(video_path).expanduser().resolve()),
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
        model = WhisperModel(model_size.strip() or "medium", device=model_device, compute_type="int8")
        segments = self._transcribe_with_vad_fallback(
            model=model,
            audio_path=str(audio_path),
            language=language.strip() or None,
            vad_filter=vad_filter,
        )

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

        if not blocks:
            raise RuntimeError(f"ASR không nhận diện được subtitle từ video: {video_path}")
        return write_srt_blocks(blocks, str(target))

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


def _is_missing_vad_asset_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "silero_vad" in message
        or ("vad" in message and "no_suchfile" in message)
        or ("vad" in message and "file doesn't exist" in message)
        or ("vad" in message and "file does not exist" in message)
    )
