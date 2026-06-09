from __future__ import annotations

import shutil
from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, run_ffmpeg
from app.modules.douyin_reup.asr_service import ASRService
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem, SubtitleSourceResult
from app.utils.file_utils import ensure_dir


class SubtitleSourceDetector:
    def __init__(self, asr_service: ASRService | None = None) -> None:
        self.asr_service = asr_service or ASRService()

    def detect_source(
        self,
        video: DouyinVideoItem,
        settings: DouyinReupSettings,
        work_dir: str,
    ) -> SubtitleSourceResult:
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
                    )
                    return SubtitleSourceResult(
                        video_path=video.path,
                        source_type="asr",
                        source_srt_path=path,
                        language=settings.source_language,
                        warnings=[*warnings, *getattr(self.asr_service, "warnings", [])],
                    )
                except Exception as exc:
                    errors.append(f"ASR thất bại cho {video.filename}: {exc}")

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
