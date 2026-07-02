from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PIL import Image

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.frame_sampler import FrameSampler
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRFrameResult, OCRRegion
from app.modules.hardsub_ocr.ocr_line_merger import OCRLineMerger
from app.modules.hardsub_ocr.ocr_provider import BaseOCRProvider, build_ocr_provider
from app.modules.hardsub_ocr.ocr_srt_builder import OCRSRTBuilder
from app.modules.hardsub_ocr.subtitle_region_detector import SubtitleRegionDetector
from app.utils.file_utils import ensure_dir, write_json


class HardSubOCRService:
    def __init__(
        self,
        frame_sampler: FrameSampler | None = None,
        region_detector: SubtitleRegionDetector | None = None,
        line_merger: OCRLineMerger | None = None,
        srt_builder: OCRSRTBuilder | None = None,
        provider: BaseOCRProvider | None = None,
    ) -> None:
        self.frame_sampler = frame_sampler or FrameSampler()
        self.region_detector = region_detector or SubtitleRegionDetector()
        self.line_merger = line_merger or OCRLineMerger()
        self.srt_builder = srt_builder
        self.provider = provider

    def extract_hardsub_to_srt(
        self,
        video_path: str,
        output_dir: str,
        settings: DouyinReupSettings,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> HardSubOCRResult:
        warnings: list[str] = []
        errors: list[str] = []
        target_dir = ensure_dir(output_dir)
        _progress(progress_callback, "ocr_probe", 2)
        media = probe_video(video_path)
        _progress(progress_callback, "ocr_loading_model", 5)
        provider = self.provider
        if provider is None:
            try:
                provider = build_ocr_provider(settings.ocr_provider, settings.ocr_language)
            except Exception as exc:
                if str(settings.ocr_provider or "").strip().lower() != "paddleocr":
                    raise
                warnings.append(f"PaddleOCR chưa sẵn sàng ({exc}); tự thử EasyOCR cho video này.")
                try:
                    provider = build_ocr_provider("easyocr", settings.ocr_language)
                except Exception as fallback_exc:
                    raise RuntimeError(f"PaddleOCR lỗi: {exc}; EasyOCR dự phòng cũng lỗi: {fallback_exc}") from fallback_exc

        _progress(progress_callback, "ocr_sampling_frames", 10)
        try:
            frames = self.frame_sampler.sample_frames(
                video_path,
                str(target_dir / "ocr_frames"),
                sample_fps=settings.ocr_sample_fps,
                max_frames=settings.ocr_max_sample_frames,
            )
        except TypeError as exc:
            if "max_frames" not in str(exc):
                raise
            frames = self.frame_sampler.sample_frames(
                video_path,
                str(target_dir / "ocr_frames"),
                sample_fps=settings.ocr_sample_fps,
            )
        frame_width, frame_height = media.width, media.height
        if frames:
            try:
                with Image.open(frames[0][1]) as image:
                    frame_width, frame_height = image.size
            except OSError:
                pass
        manual_region = settings.ocr_manual_region
        if manual_region and (frame_width != media.width or frame_height != media.height):
            scale_x = frame_width / max(1, media.width)
            scale_y = frame_height / max(1, media.height)
            manual_region = {
                "x": int(float(manual_region.get("x", 0)) * scale_x),
                "y": int(float(manual_region.get("y", 0)) * scale_y),
                "width": int(float(manual_region.get("width", media.width)) * scale_x),
                "height": int(float(manual_region.get("height", media.height)) * scale_y),
            }
        requested_region_mode = settings.ocr_region_mode
        region = self.region_detector.detect_region(
            frame_width,
            frame_height,
            mode=requested_region_mode,
            manual_region=manual_region,
        )
        _progress(progress_callback, "ocr_recognizing", 20)
        frame_results: list[OCRFrameResult] = []
        total_frames = max(1, len(frames))
        frames_to_process = frames
        if type(provider).recognize_batch is not BaseOCRProvider.recognize_batch:
            batch_size = 4
            for batch_start in range(0, len(frames), batch_size):
                batch = frames[batch_start : batch_start + batch_size]
                try:
                    recognized = provider.recognize_batch([frame_path for _timestamp, frame_path in batch], region)
                except Exception as exc:
                    recognized = [
                        OCRFrameResult(
                            timestamp_ms=timestamp_ms,
                            frame_path=frame_path,
                            region=region,
                            text="",
                            confidence=0.0,
                            warnings=[f"OCR frame error: {exc}"],
                        )
                        for timestamp_ms, frame_path in batch
                    ]
                for (timestamp_ms, _frame_path), result in zip(batch, recognized):
                    if result.timestamp_ms != timestamp_ms:
                        result = result.model_copy(update={"timestamp_ms": timestamp_ms})
                    frame_results.append(result)
                    warnings.extend(result.warnings)
                completed_frames = min(len(frames), batch_start + len(batch))
                percent = 20 + int((completed_frames / total_frames) * 72)
                _progress(progress_callback, "ocr_recognizing", min(92, percent), completed_frames, total_frames)
            frames_to_process = []

        for frame_index, (timestamp_ms, frame_path) in enumerate(frames_to_process, start=1):
            try:
                result = provider.recognize(frame_path, region)
                if result.timestamp_ms != timestamp_ms:
                    result = result.model_copy(update={"timestamp_ms": timestamp_ms})
                frame_results.append(result)
                warnings.extend(result.warnings)
            except Exception as exc:
                frame_results.append(
                    OCRFrameResult(
                        timestamp_ms=timestamp_ms,
                        frame_path=frame_path,
                        region=region,
                        text="",
                        confidence=0.0,
                        warnings=[f"OCR frame lỗi: {exc}"],
                    )
                )
                warnings.append(f"OCR frame lỗi: {exc}")

            if frame_index == total_frames or frame_index % max(1, total_frames // 15) == 0:
                percent = 20 + int((frame_index / total_frames) * 72)
                _progress(progress_callback, "ocr_recognizing", min(92, percent), frame_index, total_frames)

        _progress(progress_callback, "ocr_merging_lines", 95, len(frames), len(frames))
        lines = self.line_merger.merge_frames_to_lines(frame_results, settings)
        filter_summary = dict(getattr(self.line_merger, "last_filter_summary", {}) or {})
        watermark_removed_count = int(filter_summary.get("watermark_removed_frame_count", 0) or 0)
        fallback_attempts: list[dict[str, Any]] = []
        effective_region_mode = requested_region_mode
        if watermark_removed_count:
            warnings.append(
                f"ocr_watermark_filtered: removed watermark/channel label text from {watermark_removed_count} OCR frame(s) before translation."
            )
        text_frame_count = sum(1 for frame in frame_results if str(frame.text or "").strip())
        accepted_frame_count = sum(line.frame_count for line in lines)
        if text_frame_count and accepted_frame_count < max(1, int(text_frame_count * 0.35)):
            warnings.append(
                "ocr_low_coverage: OCR thấy nhiều frame có chữ nhưng chỉ giữ được ít dòng phụ đề tin cậy. "
                "Hãy tăng Sample FPS, dùng vùng OCR thủ công hoặc kiểm tra lại độ rõ của chữ trên video."
            )
        low_confidence_line_count = sum(
            1
            for line in lines
            if any("ocr_low_confidence_candidate" in warning for warning in line.warnings)
        )
        if low_confidence_line_count:
            warnings.append(
                f"ocr_low_confidence_lines: Đã giữ {low_confidence_line_count} dòng OCR confidence thấp "
                "vì vẫn có đủ dấu hiệu chữ Trung; cần review kỹ bản dịch."
            )
        if _should_retry_full_frame(
            requested_region_mode=requested_region_mode,
            line_count=len(lines),
            average_confidence=sum(line.confidence for line in lines) / len(lines) if lines else 0.0,
            text_frame_count=text_frame_count,
            accepted_frame_count=accepted_frame_count,
        ):
            fallback_region = self.region_detector.detect_region(frame_width, frame_height, mode="full_frame")
            _progress(progress_callback, "ocr_retry_full_frame", 92, len(frames), len(frames))
            fallback_frame_results, fallback_warnings = _recognize_frames_for_region(
                provider,
                frames,
                fallback_region,
                progress_callback,
            )
            fallback_lines = self.line_merger.merge_frames_to_lines(fallback_frame_results, settings)
            fallback_filter_summary = dict(getattr(self.line_merger, "last_filter_summary", {}) or {})
            fallback_average_confidence = (
                sum(line.confidence for line in fallback_lines) / len(fallback_lines) if fallback_lines else 0.0
            )
            fallback_text_frame_count = sum(1 for frame in fallback_frame_results if str(frame.text or "").strip())
            fallback_accepted_frame_count = sum(line.frame_count for line in fallback_lines)
            fallback_used = _fallback_result_is_better(
                current_line_count=len(lines),
                current_average_confidence=sum(line.confidence for line in lines) / len(lines) if lines else 0.0,
                current_accepted_frame_count=accepted_frame_count,
                fallback_line_count=len(fallback_lines),
                fallback_average_confidence=fallback_average_confidence,
                fallback_accepted_frame_count=fallback_accepted_frame_count,
            )
            fallback_attempts.append(
                {
                    "region_mode": "full_frame",
                    "region": fallback_region.model_dump(mode="json"),
                    "detected_line_count": len(fallback_lines),
                    "average_confidence": round(fallback_average_confidence, 4),
                    "text_frame_count": fallback_text_frame_count,
                    "accepted_frame_count": fallback_accepted_frame_count,
                    "used": fallback_used,
                }
            )
            if fallback_used:
                region = fallback_region
                frame_results = fallback_frame_results
                lines = fallback_lines
                filter_summary = fallback_filter_summary
                text_frame_count = fallback_text_frame_count
                accepted_frame_count = fallback_accepted_frame_count
                effective_region_mode = "full_frame"
                warnings.extend(fallback_warnings)
                warnings.append(
                    "ocr_region_fallback_full_frame: initial OCR region was weak, retried full-frame and used the stronger result."
                )
        if provider.provider_name == "paddleocr" and not lines and frames:
            try:
                easy_provider = build_ocr_provider("easyocr", settings.ocr_language)
                easy_region = self.region_detector.detect_region(frame_width, frame_height, mode="full_frame")
                _progress(progress_callback, "ocr_retry_easyocr", 93, len(frames), len(frames))
                easy_frame_results, easy_warnings = _recognize_frames_for_region(
                    easy_provider,
                    frames,
                    easy_region,
                    progress_callback,
                )
                easy_lines = self.line_merger.merge_frames_to_lines(easy_frame_results, settings)
                easy_filter_summary = dict(getattr(self.line_merger, "last_filter_summary", {}) or {})
                easy_average_confidence = sum(line.confidence for line in easy_lines) / len(easy_lines) if easy_lines else 0.0
                easy_text_frame_count = sum(1 for frame in easy_frame_results if str(frame.text or "").strip())
                easy_accepted_frame_count = sum(line.frame_count for line in easy_lines)
                easy_used = bool(easy_lines)
                fallback_attempts.append(
                    {
                        "provider": "easyocr",
                        "region_mode": "full_frame",
                        "region": easy_region.model_dump(mode="json"),
                        "detected_line_count": len(easy_lines),
                        "average_confidence": round(easy_average_confidence, 4),
                        "text_frame_count": easy_text_frame_count,
                        "accepted_frame_count": easy_accepted_frame_count,
                        "used": easy_used,
                    }
                )
                if easy_used:
                    provider = easy_provider
                    region = easy_region
                    frame_results = easy_frame_results
                    lines = easy_lines
                    filter_summary = easy_filter_summary
                    text_frame_count = easy_text_frame_count
                    accepted_frame_count = easy_accepted_frame_count
                    effective_region_mode = "full_frame"
                    warnings.extend(easy_warnings)
                    warnings.append("ocr_provider_fallback_easyocr: PaddleOCR không ra phụ đề, đã dùng EasyOCR full-frame.")
            except Exception as exc:
                warnings.append(f"EasyOCR fallback sau PaddleOCR không thành công: {exc}")
        average_confidence = sum(line.confidence for line in lines) / len(lines) if lines else 0.0
        source_srt_path = None
        if lines:
            builder = self.srt_builder or OCRSRTBuilder(min_duration_ms=settings.ocr_min_duration_ms)
            source_srt_path = builder.build_srt(
                lines,
                str(target_dir / f"{Path(video_path).stem}_source_{settings.source_language}_ocr.srt"),
                video_duration_ms=int(media.duration * 1000),
            )
        else:
            errors.append("OCR không nhận diện được phụ đề tiếng Trung đủ tin cậy.")

        debug_path = target_dir / f"{Path(video_path).stem}_ocr_debug.json"
        payload = {
            "video_path": video_path,
            "provider": provider.provider_name,
            "language": settings.ocr_language,
            "requested_region_mode": requested_region_mode,
            "region_mode": effective_region_mode,
            "region": region.model_dump(mode="json"),
            "frame_width": frame_width,
            "frame_height": frame_height,
            "sample_fps": settings.ocr_sample_fps,
            "frame_count": len(frames),
            "detected_line_count": len(lines),
            "average_confidence": round(average_confidence, 4),
            "source_srt_path": source_srt_path,
            "filter_summary": filter_summary,
            "fallback_attempts": fallback_attempts,
            "frames": [
                {
                    "timestamp_ms": frame.timestamp_ms,
                    "region": frame.region.model_dump(mode="json"),
                    "text": frame.text,
                    "confidence": frame.confidence,
                    "raw_blocks": frame.raw_blocks,
                    "warnings": frame.warnings,
                }
                for frame in frame_results
            ],
            "lines": [line.model_dump(mode="json") for line in lines],
            "warnings": warnings,
            "errors": errors,
        }
        write_json(debug_path, payload)
        _progress(progress_callback, "ocr_completed", 100, len(frames), len(frames))

        return HardSubOCRResult(
            video_path=video_path,
            provider=provider.provider_name,
            language=settings.ocr_language,
            region_mode=effective_region_mode,
            source_srt_path=source_srt_path,
            debug_json_path=str(debug_path),
            frame_count=len(frames),
            detected_line_count=len(lines),
            average_confidence=average_confidence,
            lines=lines,
            warnings=warnings,
            errors=errors,
        )


def _progress(
    callback: Callable[[dict[str, Any]], None] | None,
    step: str,
    progress: int,
    completed_frames: int = 0,
    total_frames: int = 0,
) -> None:
    if callback:
        callback(
            {
                "current_step": step,
                "progress": max(0, min(100, int(progress))),
                "completed_frames": completed_frames,
                "total_frames": total_frames,
            }
        )


def _recognize_frames_for_region(
    provider: BaseOCRProvider,
    frames: list[tuple[int, str]],
    region: OCRRegion,
    progress_callback: Callable[[dict[str, Any]], None] | None,
) -> tuple[list[OCRFrameResult], list[str]]:
    frame_results: list[OCRFrameResult] = []
    warnings: list[str] = []
    total_frames = max(1, len(frames))
    frames_to_process = frames
    if type(provider).recognize_batch is not BaseOCRProvider.recognize_batch:
        batch_size = 4
        for batch_start in range(0, len(frames), batch_size):
            batch = frames[batch_start : batch_start + batch_size]
            try:
                recognized = provider.recognize_batch([frame_path for _timestamp, frame_path in batch], region)
            except Exception as exc:
                recognized = [
                    OCRFrameResult(
                        timestamp_ms=timestamp_ms,
                        frame_path=frame_path,
                        region=region,
                        text="",
                        confidence=0.0,
                        warnings=[f"OCR frame error: {exc}"],
                    )
                    for timestamp_ms, frame_path in batch
                ]
            for (timestamp_ms, _frame_path), result in zip(batch, recognized):
                if result.timestamp_ms != timestamp_ms:
                    result = result.model_copy(update={"timestamp_ms": timestamp_ms})
                frame_results.append(result)
                warnings.extend(result.warnings)
            completed_frames = min(len(frames), batch_start + len(batch))
            percent = 92 + int((completed_frames / total_frames) * 3)
            _progress(progress_callback, "ocr_retry_full_frame", min(95, percent), completed_frames, total_frames)
        frames_to_process = []

    for frame_index, (timestamp_ms, frame_path) in enumerate(frames_to_process, start=1):
        try:
            result = provider.recognize(frame_path, region)
            if result.timestamp_ms != timestamp_ms:
                result = result.model_copy(update={"timestamp_ms": timestamp_ms})
            frame_results.append(result)
            warnings.extend(result.warnings)
        except Exception as exc:
            frame_results.append(
                OCRFrameResult(
                    timestamp_ms=timestamp_ms,
                    frame_path=frame_path,
                    region=region,
                    text="",
                    confidence=0.0,
                    warnings=[f"OCR frame error: {exc}"],
                )
            )
            warnings.append(f"OCR frame error: {exc}")

        if frame_index == total_frames or frame_index % max(1, total_frames // 15) == 0:
            percent = 92 + int((frame_index / total_frames) * 3)
            _progress(progress_callback, "ocr_retry_full_frame", min(95, percent), frame_index, total_frames)
    return frame_results, warnings


def _should_retry_full_frame(
    *,
    requested_region_mode: str,
    line_count: int,
    average_confidence: float,
    text_frame_count: int,
    accepted_frame_count: int,
) -> bool:
    mode = (requested_region_mode or "").strip().lower()
    if mode in {"full_frame", "manual"}:
        return False
    if line_count <= 0:
        return True
    if average_confidence < 0.12:
        return True
    return bool(text_frame_count and accepted_frame_count < max(1, int(text_frame_count * 0.35)))


def _fallback_result_is_better(
    *,
    current_line_count: int,
    current_average_confidence: float,
    current_accepted_frame_count: int,
    fallback_line_count: int,
    fallback_average_confidence: float,
    fallback_accepted_frame_count: int,
) -> bool:
    if fallback_line_count <= 0:
        return False
    if current_line_count <= 0:
        return True
    if fallback_line_count >= current_line_count + 2:
        return fallback_average_confidence >= max(0.02, current_average_confidence * 0.5)
    if fallback_line_count >= current_line_count and fallback_average_confidence >= current_average_confidence + 0.05:
        return True
    return (
        current_average_confidence < 0.12
        and fallback_line_count >= current_line_count
        and fallback_accepted_frame_count > current_accepted_frame_count
    )
