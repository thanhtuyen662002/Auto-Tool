from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.frame_sampler import FrameSampler
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult, OCRFrameResult
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
    ) -> HardSubOCRResult:
        warnings: list[str] = []
        errors: list[str] = []
        target_dir = ensure_dir(output_dir)
        media = probe_video(video_path)
        region = self.region_detector.detect_region(
            media.width,
            media.height,
            mode=settings.ocr_region_mode,
            manual_region=settings.ocr_manual_region,
        )
        provider = self.provider or build_ocr_provider(settings.ocr_provider, settings.ocr_language)

        frames = self.frame_sampler.sample_frames(
            video_path,
            str(target_dir / "ocr_frames"),
            sample_fps=settings.ocr_sample_fps,
        )
        frame_results: list[OCRFrameResult] = []
        for timestamp_ms, frame_path in frames:
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

        lines = self.line_merger.merge_frames_to_lines(frame_results, settings)
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
            "region_mode": settings.ocr_region_mode,
            "region": region.model_dump(mode="json"),
            "sample_fps": settings.ocr_sample_fps,
            "frame_count": len(frames),
            "detected_line_count": len(lines),
            "average_confidence": round(average_confidence, 4),
            "source_srt_path": source_srt_path,
            "frames": [
                {
                    "timestamp_ms": frame.timestamp_ms,
                    "text": frame.text,
                    "confidence": frame.confidence,
                    "warnings": frame.warnings,
                }
                for frame in frame_results
            ],
            "lines": [line.model_dump(mode="json") for line in lines],
            "warnings": warnings,
            "errors": errors,
        }
        write_json(debug_path, payload)

        return HardSubOCRResult(
            video_path=video_path,
            provider=provider.provider_name,
            language=settings.ocr_language,
            region_mode=settings.ocr_region_mode,
            source_srt_path=source_srt_path,
            debug_json_path=str(debug_path),
            frame_count=len(frames),
            detected_line_count=len(lines),
            average_confidence=average_confidence,
            lines=lines,
            warnings=warnings,
            errors=errors,
        )
