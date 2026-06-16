from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.douyin_reup.asr_service import ASRService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.hardsub_ocr import HardSubOCRService
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult
from app.utils.file_utils import ensure_dir
from app.utils.process_isolation import run_in_isolated_process


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
                    warnings.append(f"Không thể trích xuất subtitle nhúng từ {video.filename}: {_compact_worker_error(exc)}")

            if source_type == "asr" and settings.use_asr_if_no_subtitle:
                try:
                    asr_payload = self._run_asr(video, settings, target_dir, progress_callback)
                    path = asr_payload["path"]
                    asr_result = SubtitleSourceResult(
                        video_path=video.path,
                        source_type="asr",
                        source_srt_path=path,
                        language=settings.source_language,
                        warnings=[*warnings, *asr_payload.get("warnings", [])],
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
                    errors.append(f"ASR thất bại cho {video.filename}: {_compact_worker_error(exc)}")
                    if settings.use_ocr_if_asr_failed:
                        ocr_result = self._try_ocr(video, settings, target_dir, "ASR lỗi nên thử OCR hard-sub.", errors)
                        if ocr_result:
                            return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

            if source_type == "ocr_hardsub" and settings.use_ocr_if_no_subtitle:
                ocr_result = self._try_ocr(video, settings, target_dir, "Không có nguồn subtitle trước bước OCR fallback.", errors)
                if ocr_result:
                    return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

        return SubtitleSourceResult(
            video_path=video.path,
            source_type="none",
            source_srt_path=None,
            language=settings.source_language,
            warnings=warnings,
            errors=_dedupe_messages(errors) or [f"Không tìm thấy subtitle cho video {video.filename}."],
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
            result = self._run_ocr(video, settings, target_dir, progress_callback)
        except Exception as exc:
            if error_sink is not None:
                error_sink.append(f"OCR hard-sub thất bại cho {video.filename}: {_compact_worker_error(exc)}")
            return None
        if not result.source_srt_path or result.detected_line_count <= 0:
            if error_sink is not None:
                error_sink.extend(_dedupe_messages(result.errors or [f"OCR hard-sub không nhận diện được phụ đề cho {video.filename}."]))
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
            errors=_dedupe_messages(result.errors),
        )

    def _run_asr(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None,
    ) -> dict[str, Any]:
        output_path = str(target_dir / f"{Path(video.path).stem}_asr_{settings.source_language}.srt")
        if settings.asr_subprocess_isolation:
            return run_in_isolated_process(
                _asr_worker,
                video.path,
                output_path,
                settings.model_dump(mode="json"),
                timeout_seconds=settings.asr_timeout_seconds,
                stage_name=f"ASR {video.filename}",
            )
        path = self.asr_service.transcribe_to_srt(
            video.path,
            output_path,
            language=settings.source_language,
            provider=settings.asr_provider,
            model_size=settings.asr_model_size,
            device=settings.asr_device,
            vad_filter=settings.asr_vad_filter,
            max_audio_seconds=settings.asr_max_audio_seconds,
            progress_callback=progress_callback,
        )
        return {"path": path, "warnings": list(getattr(self.asr_service, "warnings", []))}

    def _run_ocr(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None,
    ) -> HardSubOCRResult:
        if settings.ocr_subprocess_isolation:
            payload = run_in_isolated_process(
                _ocr_worker,
                video.path,
                str(target_dir),
                settings.model_dump(mode="json"),
                timeout_seconds=settings.ocr_timeout_seconds,
                stage_name=f"OCR {video.filename}",
            )
            return HardSubOCRResult.model_validate(payload)
        if progress_callback is None:
            return self.ocr_service.extract_hardsub_to_srt(video.path, str(target_dir), settings)
        return self.ocr_service.extract_hardsub_to_srt(
            video.path,
            str(target_dir),
            settings,
            progress_callback=progress_callback,
        )


def _srt_line_count(path: str) -> int:
    try:
        return len(parse_srt_blocks(path))
    except Exception:
        return 0


def _compact_worker_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    for marker in ("Traceback (most recent call last):", "Traceback"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    if "ASR không nhận diện được subtitle từ video" in text:
        return "ASR không nhận diện được phụ đề từ audio của video."
    if "OCR không nhận diện được" in text:
        return "OCR không nhận diện được phụ đề tiếng Trung đủ tin cậy."
    return text[:700] if len(text) > 700 else text


def _dedupe_messages(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values or []:
        text = " ".join(str(value).split())
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _asr_worker(video_path: str, output_srt_path: str, settings_payload: dict[str, Any]) -> dict[str, Any]:
    settings = DouyinReupSettings.model_validate(settings_payload)
    service = ASRService()
    path = service.transcribe_to_srt(
        video_path,
        output_srt_path,
        language=settings.source_language,
        provider=settings.asr_provider,
        model_size=settings.asr_model_size,
        device=settings.asr_device,
        vad_filter=settings.asr_vad_filter,
        max_audio_seconds=settings.asr_max_audio_seconds,
        progress_callback=None,
    )
    return {"path": path, "warnings": list(service.warnings)}


def _ocr_worker(video_path: str, output_dir: str, settings_payload: dict[str, Any]) -> dict[str, Any]:
    settings = DouyinReupSettings.model_validate(settings_payload)
    result = HardSubOCRService().extract_hardsub_to_srt(video_path, output_dir, settings, progress_callback=None)
    return result.model_dump(mode="json")
