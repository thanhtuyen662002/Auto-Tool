from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_folder_scanner import DouyinFolderScanner
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.silent_immersive_reup.silent_reup_pipeline import SilentReupPipeline
from app.modules.silent_immersive_reup.silent_schema import SilentReupPlan, SpeechPresenceResult
from app.modules.silent_immersive_reup.speech_presence_detector import SpeechPresenceDetector
from app.utils.file_utils import ensure_dir


SILENT_PRESET_IDS = {"silent_chill_immersive", "silent_product_voiceover", "silent_sales_recut"}


class SilentReupService:
    def __init__(
        self,
        scanner: DouyinFolderScanner | None = None,
        detector: SpeechPresenceDetector | None = None,
        pipeline: SilentReupPipeline | None = None,
    ) -> None:
        self.scanner = scanner or DouyinFolderScanner()
        self.detector = detector or SpeechPresenceDetector()
        self.pipeline = pipeline or SilentReupPipeline(speech_detector=self.detector)

    def detect_folder(self, source_folder: str) -> list[dict]:
        items = []
        for video in self.scanner.scan_folder(source_folder):
            result = self.detector.detect(video.path)
            items.append(
                {
                    "video_path": video.path,
                    "has_speech": result.has_speech,
                    "speech_score": result.speech_score,
                    "recommended_mode": "normal_asr" if result.has_speech else "silent_immersive",
                    "method": result.method,
                    "warnings": result.warnings,
                }
            )
        return items

    def build_plan(
        self,
        video_path: str,
        settings: DouyinReupSettings | None = None,
        output_dir: str | None = None,
        product_context: dict | None = None,
    ) -> SilentReupPlan:
        settings = settings or DouyinReupSettings(enabled=True)
        target_dir = ensure_dir(output_dir or Path(video_path).with_suffix("").parent / "_silent_reup_plan" / Path(video_path).stem)
        return self.pipeline.build_plan(video_path, settings, str(target_dir), product_context)


def is_silent_reup_settings(settings: DouyinReupSettings) -> bool:
    return bool(settings.enable_silent_immersive_mode and (settings.preset_id or "").strip() in SILENT_PRESET_IDS)


def speech_result_for_video(video_path: str, settings: DouyinReupSettings) -> SpeechPresenceResult:
    return SpeechPresenceDetector(threshold=settings.speech_detection_threshold).detect(video_path)
