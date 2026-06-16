from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.douyin_reup.asr_service import ASRService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.hardsub_ocr import HardSubOCRService
from app.utils.file_utils import ensure_dir


class SubtitleSourceDetector:
    def __init__(self, asr_service: ASRService | None = None, ocr_service: HardSubOCRService | None = None) -> None:
        self.asr_service = asr_service or ASRService()
        self.ocr_service = ocr_service or HardSubOCRService()

    def detect_source(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        work_dir: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> SubtitleSourceResult:
        self._progress_callback = progress_callback
        target_dir = ensure_dir(work_dir)
        warnings: list[str] = []
        errors: list[str] = []

        for source_type in settings.subtitle_source_priority:
            if source_type == "sidecar_srt" and settings.use_sidecar_srt:
                result = self._copy_sidecar(video, settings, target_dir)
                if result:
                    return result

            if source_type == "embedded_subtitle" and settings.use_embedded_subtitle:
                if not video.embedded_subtitle_found:
                    continue
                try:
                    path = self._extract_embedded(video, target_dir)
                    return SubtitleSourceResult(
                        video_path=video.path,
                        source_type="embedded_subtitle",
                        source_srt_path=path,
                        language=settings.source_language,
                    )
                except (FFmpegError, OSError, ValueError) as exc:
                    warnings.append(f"Không thể trích xuất subtitle nhúng từ {video.filename}: {exc}")

            if source_type == "asr" and settings.use_asr_if_no_subtitle:
                try:
                    path = self.asr_service.transcribe_to_srt(
                        video.path,
                        str(target_dir / f"{Path(video.path).stem}_asr_{settings.source_language}.srt"),
                        language=settings.source_language,
                        provider=settings.asr_provider,
                        model_size=settings.asr_model_size,
                        device=settings.asr_device,
                        vad_filter=settings.asr_vad_filter,
                        max_audio_seconds=settings.asr_max_audio_seconds,
                        progress_callback=progress_callback,
                    )
                    asr_result = SubtitleSourceResult(
                        video_path=video.path,
                        source_type="asr",
                        source_srt_path=path,
                        language=settings.source_language,
                        warnings=[*warnings, *getattr(self.asr_service, "warnings", [])],
                    )
                    if settings.prefer_ocr_over_asr_when_text_visible:
                        ocr_result = self._try_ocr(video, settings, target_dir, "OCR được ưu tiên hơn ASR theo cấu hình.", errors)
                        if ocr_result:
                            return ocr_result
                    asr_line_count = _srt_line_count(path)
                    if settings.use_ocr_if_asr_failed and asr_line_count < 2:
                        ocr_result = self._try_ocr(video, settings, target_dir, "ASR tạo quá ít dòng, thử OCR hard-sub.", errors)
                        if ocr_result and ocr_result.ocr_detected_line_count > asr_line_count:
                            return ocr_result
                    return asr_result
                except Exception as exc:
                    errors.append(f"ASR thất bại cho {video.filename}: {exc}")
                    if settings.use_ocr_if_asr_failed:
                        ocr_result = self._try_ocr(video, settings, target_dir, "ASR failed and OCR detected Chinese hard subtitles.", errors)
                        if ocr_result:
                            return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

            if source_type == "ocr_hardsub" and settings.use_ocr_if_no_subtitle:
                ocr_result = self._try_ocr(video, settings, target_dir, "No subtitle source found before OCR fallback.", errors)
                if ocr_result:
                    return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

        return SubtitleSourceResult(
            video_path=video.path,
            source_type="none",
            source_srt_path=None,
            language=settings.source_language,
            warnings=warnings,
            errors=errors or [f"Không tìm thấy subtitle cho video {video.filename}."],
        )

    def _copy_sidecar(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
    ) -> SubtitleSourceResult | None:
        if not video.sidecar_srt_path:
            return None
        source = Path(video.sidecar_srt_path)
        if not source.exists() or source.stat().st_size <= 0:
            return None
        target = target_dir / f"{Path(video.path).stem}_source_{settings.source_language}.srt"
        shutil.copy2(source, target)
        return SubtitleSourceResult(
            video_path=video.path,
            source_type="sidecar_srt",
            source_srt_path=str(target),
            language=settings.source_language,
        )

    def _extract_embedded(self, video: DouyinVideoItem, target_dir: Path) -> str:
        target = target_dir / f"{Path(video.path).stem}_embedded.srt"
        run_ffmpeg(
            [
                "-y",
                "-i",
                video.path,
                "-map",
                "0:s:0",
                str(target),
            ]
        )
        if not target.exists() or target.stat().st_size <= 0:
            raise RuntimeError("File subtitle nhúng sau khi trích xuất bị rỗng.")
        return str(target)

    def _try_ocr(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        reason: str,
        error_sink: list[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> SubtitleSourceResult | None:
        progress_callback = progress_callback or getattr(self, "_progress_callback", None)
        try:
            if progress_callback is None:
                result = self.ocr_service.extract_hardsub_to_srt(video.path, str(target_dir), settings)
            else:
                result = self.ocr_service.extract_hardsub_to_srt(
                    video.path,
                    str(target_dir),
                    settings,
                    progress_callback=progress_callback,
                )
        except Exception as exc:
            if error_sink is not None:
                error_sink.append(f"OCR hard-sub thất bại cho {video.filename}: {exc}")
            return None
        if not result.source_srt_path or result.detected_line_count <= 0:
            if error_sink is not None:
                error_sink.extend(result.errors or [f"OCR hard-sub không nhận diện được phụ đề cho {video.filename}."])
            return None
        return SubtitleSourceResult(
            video_path=video.path,
            source_type="ocr_hardsub",
            source_srt_path=result.source_srt_path,
            language=settings.source_language,
            ocr_debug_json_path=result.debug_json_path,
            ocr_frame_count=result.frame_count,
            ocr_detected_line_count=result.detected_line_count,
            ocr_average_confidence=result.average_confidence,
            warnings=[
                reason,
                "Phụ đề nguồn được nhận diện bằng OCR từ chữ dính trên video. Vui lòng kiểm tra kỹ vì OCR có thể nhận sai chữ.",
                *result.warnings,
            ],
            errors=result.errors,
        )


def _srt_line_count(path: str) -> int:
    try:
        return len(parse_srt_blocks(path))
    except Exception:
        return 0
