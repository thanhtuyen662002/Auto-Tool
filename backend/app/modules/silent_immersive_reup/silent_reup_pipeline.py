from __future__ import annotations

import json
from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, write_srt_blocks
from app.modules.douyin_reup.subtitle_translator import SubtitleTranslator
from app.modules.hardsub_ocr import HardSubOCRService
from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine, VoiceoverLine
from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.immersive_scene_classifier import ImmersiveSceneClassifier
from app.modules.silent_immersive_reup.immersive_script_generator import ImmersiveScriptGenerator
from app.modules.silent_immersive_reup.silent_schema import ImmersiveCaptionLine, SilentReupPlan, SilentReupResult
from app.modules.silent_immersive_reup.speech_presence_detector import SpeechPresenceDetector
from app.modules.silent_immersive_reup.visual_segment_analyzer import VisualSegmentAnalyzer
from app.modules.tts.tts_schema import TTSSettings
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.utils.file_utils import ensure_dir, write_json


class SilentReupPipeline:
    def __init__(
        self,
        speech_detector: SpeechPresenceDetector | None = None,
        visual_analyzer: VisualSegmentAnalyzer | None = None,
        scene_classifier: ImmersiveSceneClassifier | None = None,
        caption_generator: ImmersiveCaptionGenerator | None = None,
        script_generator: ImmersiveScriptGenerator | None = None,
        ocr_service: HardSubOCRService | None = None,
        translator: SubtitleTranslator | None = None,
        render_pipeline: DouyinRenderPipeline | None = None,
        voice_generator: VoiceGenerator | None = None,
    ) -> None:
        self.speech_detector = speech_detector
        self.visual_analyzer = visual_analyzer or VisualSegmentAnalyzer()
        self.scene_classifier = scene_classifier or ImmersiveSceneClassifier()
        self.caption_generator = caption_generator or ImmersiveCaptionGenerator()
        self.script_generator = script_generator or ImmersiveScriptGenerator()
        self.ocr_service = ocr_service or HardSubOCRService()
        self.translator = translator or SubtitleTranslator()
        self.render_pipeline = render_pipeline or DouyinRenderPipeline()
        self.voice_generator = voice_generator or VoiceGenerator()
        self.last_plan_path: str | None = None
        self.last_caption_srt_path: str | None = None
        self.last_ocr_source_srt_path: str | None = None
        self.last_ocr_translated_srt_path: str | None = None
        self.last_ocr_debug_json_path: str | None = None
        self.last_ocr_frame_count = 0
        self.last_ocr_detected_line_count = 0
        self.last_ocr_average_confidence = 0.0
        self.last_voiceover_script_path: str | None = None

    def build_plan(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        output_dir: str,
        product_context: dict | None = None,
    ) -> SilentReupPlan:
        self.last_plan_path = None
        self.last_caption_srt_path = None
        self.last_ocr_source_srt_path = None
        self.last_ocr_translated_srt_path = None
        self.last_ocr_debug_json_path = None
        self.last_ocr_frame_count = 0
        self.last_ocr_detected_line_count = 0
        self.last_ocr_average_confidence = 0.0
        self.last_voiceover_script_path = None
        target_dir = ensure_dir(output_dir)
        warnings: list[str] = []

        detector = self.speech_detector or SpeechPresenceDetector(threshold=settings.speech_detection_threshold)
        if settings.detect_speech_presence:
            speech = detector.detect(video_path)
            warnings.extend(speech.warnings)
        else:
            speech = detector.detect(video_path).model_copy(
                update={
                    "has_speech": False,
                    "speech_score": 0.0,
                    "method": "disabled_by_settings",
                    "warnings": [],
                }
            )

        if speech.has_speech:
            warnings.append("Video có dấu hiệu lời thoại rõ; nên cân nhắc dùng flow ASR bình thường nếu cần dịch lời thoại.")

        segments = []
        if settings.use_visual_segments_for_silent_video:
            segments = self.visual_analyzer.analyze_video(video_path, settings, str(target_dir))
            segments = self.scene_classifier.classify_segments(segments, product_context)

        ocr_translated_srt_path = self._try_ocr_translate(video_path, settings, target_dir, warnings)
        captions = self.caption_generator.generate_captions(
            video_path=video_path,
            segments=segments,
            strategy=settings.silent_mode_strategy,
            product_context=product_context,
            ocr_translated_srt_path=ocr_translated_srt_path,
        )
        voiceover_script = None
        if settings.generate_voiceover_for_silent_video:
            voiceover_script = self.script_generator.generate_voiceover_script(
                SilentReupPlan(
                    video_path=video_path,
                    strategy=settings.silent_mode_strategy,
                    has_speech=speech.has_speech,
                    speech_score=speech.speech_score,
                    visual_segments=segments,
                    captions=captions,
                    generate_voiceover=True,
                    voiceover_script=None,
                    recommended_audio_mode="voiceover_plus_original_audio_plus_bgm",
                    warnings=warnings,
                ),
                product_context=product_context,
                style=settings.visual_caption_style,
            )
            script_path = target_dir / f"{Path(video_path).stem}_voiceover_script.txt"
            script_path.write_text(voiceover_script, encoding="utf-8")
            self.last_voiceover_script_path = str(script_path)

        plan = SilentReupPlan(
            video_path=video_path,
            strategy=settings.silent_mode_strategy,
            has_speech=speech.has_speech,
            speech_score=speech.speech_score,
            visual_segments=segments,
            captions=captions,
            generate_voiceover=settings.generate_voiceover_for_silent_video,
            voiceover_script=voiceover_script,
            recommended_audio_mode=_recommended_audio_mode(settings),
            warnings=_dedupe(warnings),
        )
        plan_path = target_dir / "silent_reup_plan.json"
        write_json(plan_path, plan.model_dump(mode="json"))
        self.last_plan_path = str(plan_path)
        return plan

    def write_caption_srt(
        self,
        plan: SilentReupPlan,
        output_dir: str,
        filename: str = "silent_reup_caption_vi.srt",
    ) -> str:
        target = ensure_dir(output_dir) / filename
        blocks = [
            SubtitleBlock(index=index, start=line.start, end=line.end, text=line.text)
            for index, line in enumerate(_normalize_caption_timing(plan.captions), start=1)
            if line.end > line.start
        ]
        if not blocks:
            raise ValueError("Silent plan không có caption hợp lệ để tạo SRT.")
        write_srt_blocks(blocks, str(target))
        self.last_caption_srt_path = str(target)
        return str(target)

    def render_from_plan(
        self,
        plan: SilentReupPlan,
        settings: DouyinReupSettings,
        output_dir: str,
    ) -> SilentReupResult:
        target_dir = ensure_dir(output_dir)
        warnings = list(plan.warnings)
        errors: list[str] = []
        caption_srt = self.write_caption_srt(plan, str(target_dir), "silent_reup_caption_vi.srt")
        voiceover_path = None
        try:
            if plan.generate_voiceover and plan.voiceover_script:
                voiceover_path = self._generate_voiceover(plan, settings, str(target_dir))
                warnings.extend(self.voice_generator.warnings)

            media = probe_video(plan.video_path)
            video = DouyinVideoItem(
                path=plan.video_path,
                filename=Path(plan.video_path).name,
                duration=media.duration,
                width=media.width,
                height=media.height,
                fps=media.fps,
                has_audio=media.has_audio,
            )
            render_settings = _render_settings_for_silent(settings)
            render_payload = self.render_pipeline.render_video_with_srt(
                video=video,
                subtitle_srt_path=caption_srt,
                settings=render_settings,
                output_dir=str(target_dir),
                output_name=f"{Path(plan.video_path).stem}_silent_reup.mp4",
                warnings=warnings,
                voiceover_path=voiceover_path,
            )
            result = SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=render_payload.get("path"),
                plan_path=self.last_plan_path,
                caption_srt_path=caption_srt,
                caption_ass_path=render_payload.get("subtitle_ass_file"),
                voiceover_path=voiceover_path,
                bgm_path=render_payload.get("bgm_file"),
                status="success",
                warnings=_dedupe(render_payload.get("warnings") or warnings),
                errors=_dedupe(render_payload.get("errors") or []),
            )
        except Exception as exc:
            errors.append(str(exc))
            result = SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=None,
                plan_path=self.last_plan_path,
                caption_srt_path=caption_srt,
                caption_ass_path=None,
                voiceover_path=voiceover_path,
                bgm_path=None,
                status="failed",
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )

        write_json(target_dir / "silent_reup_log.json", result.model_dump(mode="json"))
        return result

    def _try_ocr_translate(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        target_dir: Path,
        warnings: list[str],
    ) -> str | None:
        if not settings.use_ocr_if_no_subtitle:
            return None
        try:
            ocr_result = self.ocr_service.extract_hardsub_to_srt(video_path, str(target_dir / "ocr"), settings)
        except Exception as exc:
            warnings.append(f"OCR hard-sub cho silent mode thất bại: {exc}")
            return None
        self.last_ocr_source_srt_path = ocr_result.source_srt_path
        self.last_ocr_debug_json_path = ocr_result.debug_json_path
        self.last_ocr_frame_count = ocr_result.frame_count
        self.last_ocr_detected_line_count = ocr_result.detected_line_count
        self.last_ocr_average_confidence = ocr_result.average_confidence
        warnings.extend(ocr_result.warnings)
        if not ocr_result.source_srt_path or ocr_result.detected_line_count <= 0:
            warnings.extend(ocr_result.errors)
            return None
        translated_path = target_dir / "silent_ocr_vi.srt"
        translation = self.translator.translate_srt(
            ocr_result.source_srt_path,
            str(translated_path),
            source_language=settings.source_language,
            target_language=settings.target_language,
            provider=settings.translation_provider,
        )
        warnings.extend(translation.warnings)
        self.last_ocr_translated_srt_path = translation.translated_srt_path
        return translation.translated_srt_path

    def _generate_voiceover(self, plan: SilentReupPlan, settings: DouyinReupSettings, output_dir: str) -> str:
        lines = _voice_lines_from_script(plan)
        subtitles = [
            SubtitleLine(start_hint=line.start, end_hint=line.end, text=line.text)
            for line in _normalize_caption_timing(plan.captions)
        ]
        script = ProductVideoScript(
            hook=lines[0].text if lines else "",
            voiceover=lines,
            subtitles=subtitles,
            cta=subtitles[-1].text if subtitles else "",
            caption=" ".join(line.text for line in subtitles[:2]),
            hashtags=["#review", "#douyin", "#sanpham"],
        )
        tts_settings = TTSSettings(
            provider=settings.silent_voiceover_provider,
            fallback_provider="piper",
            voice=settings.silent_voiceover_voice,
            language=settings.target_language,
            output_format="mp3",
        )
        return self.voice_generator.generate_voiceover(
            script,
            output_dir,
            filename="silent_voiceover.mp3",
            text_filename="silent_voiceover_text.txt",
            language=settings.target_language,
            target_duration=_plan_duration(plan),
            tts_settings=tts_settings,
        )


def _render_settings_for_silent(settings: DouyinReupSettings) -> DouyinReupSettings:
    return settings.model_copy(
        update={
            "keep_original_audio": settings.keep_immersive_original_audio,
            "original_audio_volume": settings.immersive_original_audio_volume,
            "add_bgm": settings.add_bgm_for_silent_video,
            "bgm_volume": settings.immersive_bgm_volume,
            "burn_subtitle": settings.burn_subtitle,
            "add_overlay": settings.add_overlay,
        }
    )


def _recommended_audio_mode(settings: DouyinReupSettings) -> str:
    parts: list[str] = []
    if settings.generate_voiceover_for_silent_video:
        parts.append("voiceover")
    if settings.keep_immersive_original_audio:
        parts.append("original_audio")
    if settings.add_bgm_for_silent_video:
        parts.append("bgm")
    return "_plus_".join(parts) or "silent_video"


def _normalize_caption_timing(captions: list[ImmersiveCaptionLine]) -> list[ImmersiveCaptionLine]:
    normalized: list[ImmersiveCaptionLine] = []
    for caption in captions:
        start = max(0.0, float(caption.start))
        end = max(start + 0.35, float(caption.end))
        normalized.append(caption.model_copy(update={"start": round(start, 3), "end": round(end, 3)}))
    return normalized


def _voice_lines_from_script(plan: SilentReupPlan) -> list[VoiceoverLine]:
    if not plan.voiceover_script:
        return [VoiceoverLine(time_hint="", text=caption.text) for caption in plan.captions]
    sentences = [part.strip() for part in plan.voiceover_script.replace("!", ".").replace("?", ".").split(".") if part.strip()]
    duration = _plan_duration(plan)
    count = max(1, len(sentences))
    lines: list[VoiceoverLine] = []
    for index, sentence in enumerate(sentences, start=1):
        start = duration * ((index - 1) / count)
        end = duration * (index / count)
        lines.append(VoiceoverLine(time_hint=f"{start:.1f}-{end:.1f}s", text=sentence))
    return lines


def _plan_duration(plan: SilentReupPlan) -> float:
    if plan.captions:
        return max(caption.end for caption in plan.captions)
    if plan.visual_segments:
        return max(segment.end for segment in plan.visual_segments)
    return 8.0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned
