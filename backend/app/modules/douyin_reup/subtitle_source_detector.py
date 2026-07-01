from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.douyin_reup.asr_service import ASRService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult
from app.modules.douyin_reup.subtitle_quality_gate import SubtitleQualityResult, evaluate_srt_quality
from app.modules.hardsub_ocr import HardSubOCRService
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult
from app.utils.file_utils import ensure_dir
from app.utils.process_isolation import run_in_isolated_process


class SubtitleSourceDetector:
    def __init__(self, asr_service: ASRService | None = None, ocr_service: HardSubOCRService | None = None) -> None:
        self.asr_service = asr_service or ASRService()
        self.ocr_service = ocr_service or HardSubOCRService()
        self.last_probe_ocr_error: str | None = None

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
        rejected_sources: list[dict[str, Any]] = []
        attempted_ocr = False
        attempted_asr = False

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
                        subtitle_quality_score=1.0,
                    )
                except (FFmpegError, OSError, ValueError) as exc:
                    warnings.append(f"Không thể trích xuất subtitle nhúng từ {video.filename}: {_compact_worker_error(exc)}")

            if source_type == "ocr_hardsub" and settings.use_ocr_if_no_subtitle and not attempted_ocr:
                attempted_ocr = True
                ocr_result = self._try_ocr(
                    video,
                    settings,
                    target_dir,
                    "Thử OCR chữ dính trên video trước ASR.",
                    errors,
                    rejected_sources,
                )
                if ocr_result:
                    return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

            if source_type == "asr" and settings.use_asr_if_no_subtitle:
                attempted_asr = True
                asr_result = self._try_asr(video, settings, target_dir, progress_callback, warnings, errors, rejected_sources)
                if asr_result:
                    return asr_result
                if settings.use_ocr_if_asr_failed and not attempted_ocr:
                    attempted_ocr = True
                    ocr_result = self._try_ocr(
                        video,
                        settings,
                        target_dir,
                        "ASR lỗi hoặc bị loại nên thử OCR chữ dính trên video.",
                        errors,
                        rejected_sources,
                    )
                    if ocr_result:
                        return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

        # --- ULTIMATE FALLBACKS ---
        # Cứu cánh cuối cùng trước khi báo lỗi cho người dùng: thử tất cả các kênh còn lại
        if not attempted_ocr:
            attempted_ocr = True
            ocr_result = self._try_ocr(
                video,
                settings,
                target_dir,
                "Cứu cánh cuối cùng (Ultimate Fallback): Tự động thử OCR trước khi báo lỗi.",
                errors,
                rejected_sources,
            )
            if ocr_result:
                return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

        if not attempted_asr:
            attempted_asr = True
            asr_result = self._try_asr(video, settings, target_dir, progress_callback, warnings, errors, rejected_sources)
            if asr_result:
                return asr_result

        return SubtitleSourceResult(
            video_path=video.path,
            source_type="none",
            source_srt_path=None,
            language=settings.source_language,
            warnings=warnings,
            errors=_dedupe_messages(errors) or [f"Không tìm thấy nguồn phụ đề đủ tin cậy cho {video.filename}."],
            subtitle_rejected_sources=rejected_sources,
            fallback_mode="music_only_safe" if rejected_sources else None,
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
            subtitle_quality_score=1.0,
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

    def _try_asr(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None,
        warnings: list[str],
        errors: list[str],
        rejected_sources: list[dict[str, Any]],
    ) -> SubtitleSourceResult | None:
        try:
            asr_payload = self._run_asr(video, settings, target_dir, progress_callback)
        except Exception as exc:
            errors.append(f"ASR thất bại cho {video.filename}: {_compact_worker_error(exc)}")
            return None

        path = asr_payload["path"]
        quality = _evaluate_source_quality(path, source_type="asr", video=video, settings=settings)
        if not quality.ok:
            rejected_sources.append(_quality_rejection("asr", quality))
            errors.append(_quality_warning(video.filename, "ASR", quality))
            return None

        if settings.prefer_ocr_over_asr_when_text_visible:
            ocr_result = self._try_ocr(
                video,
                settings,
                target_dir,
                "OCR được ưu tiên hơn ASR theo cấu hình hiện tại.",
                errors,
                rejected_sources,
            )
            if ocr_result:
                return ocr_result.model_copy(update={"warnings": [*warnings, *ocr_result.warnings]})

        return SubtitleSourceResult(
            video_path=video.path,
            source_type="asr",
            source_srt_path=path,
            language=settings.source_language,
            warnings=[*warnings, *asr_payload.get("warnings", [])],
            subtitle_quality_score=quality.score,
            subtitle_quality_reasons=quality.reasons,
            subtitle_quality_stats=quality.stats,
            subtitle_rejected_sources=list(rejected_sources),
        )

    def _try_ocr(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        reason: str,
        error_sink: list[str] | None = None,
        rejected_sources: list[dict[str, Any]] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> SubtitleSourceResult | None:
        progress_callback = progress_callback or getattr(self, "_progress_callback", None)
        try:
            result = self._run_ocr(video, settings, target_dir, progress_callback)
        except Exception as exc:
            if error_sink is not None:
                error_sink.append(f"OCR chữ dính trên video thất bại cho {video.filename}: {_compact_worker_error(exc)}")
            return None
        if not result.source_srt_path or result.detected_line_count <= 0:
            if error_sink is not None:
                error_sink.extend(_dedupe_messages(result.errors or [f"OCR không tìm thấy phụ đề cho {video.filename}."]))
            return None

        quality = _evaluate_source_quality(
            result.source_srt_path,
            source_type="ocr_hardsub",
            video=video,
            settings=settings,
            ocr_confidence=result.average_confidence,
        )
        if not quality.ok:
            if rejected_sources is not None:
                rejected_sources.append(_quality_rejection("ocr_hardsub", quality))
            if error_sink is not None:
                error_sink.append(_quality_warning(video.filename, "OCR hard-sub", quality))
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
            ocr_region_mode=result.region_mode,
            subtitle_quality_score=quality.score,
            subtitle_quality_reasons=quality.reasons,
            subtitle_quality_stats=quality.stats,
            subtitle_rejected_sources=list(rejected_sources or []),
            warnings=[
                reason,
                "Phụ đề nguồn được đọc bằng OCR từ chữ dính trên video; hãy kiểm tra kỹ trước khi render hàng loạt.",
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
                progress_callback=progress_callback,
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

    def probe_ocr_debug(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        target_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> HardSubOCRResult | None:
        self.last_probe_ocr_error = None
        try:
            result = self._run_ocr(video, settings, target_dir, progress_callback)
        except Exception as exc:
            self.last_probe_ocr_error = _compact_worker_error(exc)
            return None
        if not result.debug_json_path:
            messages = _dedupe_messages([*result.errors, *result.warnings])
            self.last_probe_ocr_error = "; ".join(messages) if messages else None
            return None
        return result

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
                progress_callback=progress_callback,
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


def _evaluate_source_quality(
    path: str,
    *,
    source_type: str,
    video: DouyinVideoItem,
    settings: DouyinReupSettings,
    ocr_confidence: float | None = None,
) -> SubtitleQualityResult:
    if not settings.subtitle_quality_gate_enabled:
        return SubtitleQualityResult(ok=True, score=1.0, reasons=[], stats={"gate_enabled": False})
    return evaluate_srt_quality(
        path,
        source_type=source_type,
        video_duration=video.duration,
        ocr_confidence=ocr_confidence,
        min_blocks=settings.asr_quality_min_blocks if source_type == "asr" else settings.ocr_quality_min_blocks,
        min_chars=settings.asr_quality_min_chars if source_type == "asr" else settings.ocr_quality_min_chars,
        min_coverage=settings.subtitle_quality_min_coverage,
    )


def _quality_rejection(source: str, quality: SubtitleQualityResult) -> dict[str, Any]:
    return {
        "source": source,
        "score": quality.score,
        "reasons": quality.reasons,
        "stats": quality.stats,
    }


def _quality_warning(filename: str, label: str, quality: SubtitleQualityResult) -> str:
    return f"{label} bị loại cho {filename}: {', '.join(quality.reasons)}"


def _compact_worker_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    for marker in ("Traceback (most recent call last):", "Traceback"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    lowered = text.lower()
    if "no suitable python runtime" in lowered:
        return (
            "Không tìm thấy Python runtime phù hợp để cài PaddleOCR. "
            "Có thể bản app đang chạy Python khác với Python đã cài trên máy."
        )
    if "paddleocr" in lowered or "paddlepaddle" in lowered or "cài ocr packages" in lowered or "pip" in lowered:
        return text[:700] if len(text) > 700 else text
    if "ASR" in text and "subtitle" in text:
        return "ASR không nhận diện được phụ đề đủ tin cậy từ audio của video."
    if "OCR" in text:
        return "OCR không nhận diện được phụ đề dính trên video đủ tin cậy."
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


def _asr_worker(
    video_path: str,
    output_srt_path: str,
    settings_payload: dict[str, Any],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
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
        progress_callback=progress_callback,
    )
    return {"path": path, "warnings": list(service.warnings)}


def _ocr_worker(
    video_path: str,
    output_dir: str,
    settings_payload: dict[str, Any],
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    settings = DouyinReupSettings.model_validate(settings_payload)
    result = HardSubOCRService().extract_hardsub_to_srt(video_path, output_dir, settings, progress_callback=progress_callback)
    return result.model_dump(mode="json")
