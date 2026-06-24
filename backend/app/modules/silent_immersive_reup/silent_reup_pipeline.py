from __future__ import annotations

import json
import inspect
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.douyin_render_pipeline import DouyinRenderPipeline
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock, parse_srt_blocks, write_srt_blocks
from app.modules.douyin_reup.subtitle_translator import SubtitleTranslator
from app.modules.hardsub_ocr import HardSubOCRService
from app.modules.hardsub_ocr.hardsub_ocr_schema import HardSubOCRResult
from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine, VoiceoverLine
from app.modules.silent_immersive_reup.immersive_caption_generator import ImmersiveCaptionGenerator
from app.modules.silent_immersive_reup.immersive_scene_classifier import ImmersiveSceneClassifier
from app.modules.silent_immersive_reup.immersive_script_generator import ImmersiveScriptGenerator
from app.modules.silent_immersive_reup.product_detector import SilentProductDetector, merge_product_detection_context
from app.modules.silent_immersive_reup.silent_schema import (
    ImmersiveCaptionLine,
    SilentCaptionGenerationMetadata,
    SilentProductDetectionReport,
    SilentReupPlan,
    SilentReupResult,
    SilentVisualSegment,
)
from app.modules.silent_immersive_reup.speech_presence_detector import SpeechPresenceDetector
from app.modules.silent_immersive_reup.visual_segment_analyzer import VisualSegmentAnalyzer
from app.modules.subtitle_review.subtitle_review_schema import SubtitleReviewDocument
from app.modules.tts.settings_builder import voiceover_tts_settings
from app.modules.tts.tts_schema import TTSSettings
from app.modules.voice_generator.voice_generator import VoiceGenerator
from app.modules.silent_visual_tagging.visual_tag_repository import VisualTagRepository
from app.modules.silent_visual_tagging.visual_tag_schema import SilentVisualTaggingMetadata
from app.modules.silent_visual_tagging.visual_tag_service import VisualTagService
from app.utils.file_utils import ensure_dir, write_json
from app.utils.process_isolation import run_in_isolated_process
from app.version import APP_VERSION


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
        visual_tag_service: VisualTagService | None = None,
        visual_tag_repository: VisualTagRepository | None = None,
        product_detector: SilentProductDetector | None = None,
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
        self.visual_tag_service = visual_tag_service or VisualTagService()
        self.visual_tag_repository = visual_tag_repository or VisualTagRepository()
        self.product_detector = product_detector or SilentProductDetector()
        self.last_plan_path: str | None = None
        self.last_caption_srt_path: str | None = None
        self.last_ocr_source_srt_path: str | None = None
        self.last_ocr_translated_srt_path: str | None = None
        self.last_ocr_debug_json_path: str | None = None
        self.last_ocr_frame_count = 0
        self.last_ocr_detected_line_count = 0
        self.last_ocr_average_confidence = 0.0
        self.last_voiceover_script_path: str | None = None
        self.last_voiceover_subtitle_path: str | None = None
        self.recent_caption_texts: list[str] = []
        self.last_visual_tag_report = None
        self.last_visual_tag_report_id: str | None = None
        self.last_product_detection_report: SilentProductDetectionReport | None = None
        self.last_product_detection_path: str | None = None

    def build_plan(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        output_dir: str,
        product_context: dict | None = None,
        gemini_api_keys: list[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> SilentReupPlan:
        started = perf_counter()
        self.last_plan_path = None
        self.last_caption_srt_path = None
        self.last_ocr_source_srt_path = None
        self.last_ocr_translated_srt_path = None
        self.last_ocr_debug_json_path = None
        self.last_ocr_frame_count = 0
        self.last_ocr_detected_line_count = 0
        self.last_ocr_average_confidence = 0.0
        self.last_voiceover_script_path = None
        self.last_voiceover_subtitle_path = None
        self.last_visual_tag_report = None
        self.last_visual_tag_report_id = None
        self.last_product_detection_report = None
        self.last_product_detection_path = None
        target_dir = ensure_dir(output_dir)
        warnings: list[str] = []

        _progress(progress_callback, "speech_detection", 5)
        detector = self.speech_detector or SpeechPresenceDetector(threshold=settings.speech_detection_threshold)
        if hasattr(detector, "threshold"):
            detector.threshold = settings.speech_detection_threshold
        if settings.detect_speech_presence and settings.silent_mode_detection:
            speech = detector.detect(video_path)
            warnings.extend(speech.warnings)
        else:
            from app.modules.silent_immersive_reup.silent_schema import SpeechPresenceResult

            speech = SpeechPresenceResult(
                video_path=video_path,
                has_speech=False,
                speech_score=0.0,
                audio_energy_score=None,
                speech_segments_count=0,
                method="disabled_by_settings",
                warnings=[],
            )

        if speech.has_speech:
            warnings.append("Video có dấu hiệu lời thoại rõ; nên cân nhắc dùng flow ASR bình thường nếu cần dịch lời thoại.")

        _progress(progress_callback, "visual_segmentation", 20)
        segments = []
        if settings.use_visual_segments_for_silent_video:
            segments = self.visual_analyzer.analyze_video(video_path, settings, str(target_dir))

        _progress(progress_callback, "ocr", 38)
        ocr_translated_srt_path = self._try_ocr_translate(
            video_path,
            settings,
            target_dir,
            warnings,
            gemini_api_keys=gemini_api_keys,
            progress_callback=_mapped_progress_callback(progress_callback, 38, 70, "ocr"),
        )
        segments = self._attach_ocr_text_to_segments(segments)
        _progress(progress_callback, "visual_tagging", 72)
        segments = self.scene_classifier.classify_segments(segments, product_context)
        visual_tag_report = self.visual_tag_service.tag_video_segments(
            video_path,
            segments,
            product_context=product_context,
            folder_name=Path(video_path).parent.name,
            filename=Path(video_path).stem,
            ocr_text_by_segment={segment.id: segment.ocr_text or "" for segment in segments},
        )
        segments = self.visual_tag_service.apply_report_to_segments(segments, visual_tag_report)
        self.last_visual_tag_report = visual_tag_report
        try:
            self.last_visual_tag_report_id = self.visual_tag_repository.save_report(visual_tag_report)
        except Exception as exc:
            warnings.append(f"Không thể lưu visual tag report: {exc}")
        _progress(progress_callback, "product_detection", 78)
        product_detection = self.product_detector.detect(
            video_path=video_path,
            segments=segments,
            visual_tag_report=visual_tag_report,
            product_context=product_context,
            gemini_api_keys=gemini_api_keys or [],
        )
        self.last_product_detection_report = product_detection
        warnings.extend(product_detection.warnings)
        effective_product_context = merge_product_detection_context(product_context, product_detection)
        if settings.visual_caption_language.casefold() not in {"vi", "vi-vn"}:
            warnings.append("Visual caption templates are Vietnamese; visual_caption_language was normalized to vi.")
        _progress(progress_callback, "caption_generation", 84)
        if ocr_translated_srt_path or settings.generate_visual_captions:
            captions = self.caption_generator.generate_captions(
                video_path=video_path,
                segments=segments,
                strategy=settings.silent_mode_strategy,
                product_context=effective_product_context,
                ocr_translated_srt_path=ocr_translated_srt_path,
                industry=(effective_product_context or {}).get("industry") or (effective_product_context or {}).get("category"),
                tone=settings.silent_caption_tone,
                recent_caption_texts=self.recent_caption_texts,
                video_recommended_industry=visual_tag_report.recommended_industry,
                use_visual_tags=True,
            )
        else:
            captions = []
            warnings.append("Visual caption generation is disabled and OCR did not produce translated text.")
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
                product_context=effective_product_context,
                style=settings.visual_caption_style,
            )
            script_path = target_dir / f"{Path(video_path).stem}_voiceover_script.txt"
            script_path.write_text(voiceover_script, encoding="utf-8")
            self.last_voiceover_script_path = str(script_path)

        _progress(progress_callback, "quality_scoring", 92)
        quality_scores = [caption.quality_score for caption in captions if caption.quality_score is not None]
        industry = (
            str((effective_product_context or {}).get("industry") or (effective_product_context or {}).get("category") or "").strip()
            or visual_tag_report.recommended_industry
            or normalize_silent_industry(effective_product_context)
        )
        template_count = len(
            self.caption_generator.template_service.list_templates(
                industry=industry,
                strategy=settings.silent_mode_strategy,
            )
        )
        generation_warnings = [
            f"Caption {caption.index} cần review quality."
            for caption in captions
            if caption.quality_needs_review
        ]
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
            caption_generation=SilentCaptionGenerationMetadata(
                industry=industry,
                tone=settings.silent_caption_tone,
                strategy=settings.silent_mode_strategy,
                template_count_available=template_count,
                captions_generated=len(captions),
                average_quality_score=round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 1.0,
                warnings=generation_warnings,
            ),
            visual_tagging=SilentVisualTaggingMetadata(
                enabled=True,
                recommended_industry=visual_tag_report.recommended_industry or "general_product",
                recommended_strategy=visual_tag_report.recommended_strategy or settings.silent_mode_strategy,
                average_confidence=visual_tag_report.average_confidence,
                tag_sources=dict(Counter(tag.source for result in visual_tag_report.segment_results for tag in result.tags)),
                report_id=self.last_visual_tag_report_id,
                warnings=visual_tag_report.warnings,
            ),
            visual_tag_report=visual_tag_report,
            product_detection=product_detection,
            warnings=_dedupe(warnings),
        )
        self.recent_caption_texts.extend(caption.text for caption in captions)
        self.recent_caption_texts = self.recent_caption_texts[-80:]
        plan_path = target_dir / "silent_reup_plan.json"
        write_json(plan_path, plan.model_dump(mode="json"))
        self.last_plan_path = str(plan_path)
        visual_tag_report_path = target_dir / "visual_tag_report.json"
        write_json(visual_tag_report_path, visual_tag_report.model_dump(mode="json"))
        product_detection_path = target_dir / "product_detection_report.json"
        write_json(product_detection_path, product_detection.model_dump(mode="json"))
        self.last_product_detection_path = str(product_detection_path)
        caption_log_path = target_dir / "caption_generation_log.json"
        write_json(
            caption_log_path,
            {
                "version": APP_VERSION,
                "mode": "silent_immersive",
                "preset_id": settings.preset_id,
                "strategy": settings.silent_mode_strategy,
                "industry": industry,
                "status": "success" if captions else "success_with_warnings",
                "steps": ["ocr", "visual_tagging", "product_detection", "caption_generation", "quality_scoring"],
                "failed_step": None,
                "warnings": generation_warnings,
                "errors": [],
                "durations": {"total_seconds": round(perf_counter() - started, 3)},
                "paths": {
                    "plan": str(plan_path),
                    "visual_tag_report": str(visual_tag_report_path),
                    "product_detection_report": str(product_detection_path),
                    "ocr_source_srt": self.last_ocr_source_srt_path,
                    "ocr_translated_srt": self.last_ocr_translated_srt_path,
                },
                "caption_generation": plan.caption_generation.model_dump(mode="json"),
                "product_detection": product_detection.model_dump(mode="json"),
                "caption_sources": dict(Counter(caption.source for caption in captions)),
            },
        )
        write_json(
            target_dir / "silent_reup_log.json",
            _standard_silent_log(
                settings=settings,
                industry=industry,
                status="planned",
                steps=["speech_detection", "visual_segmentation", "ocr", "visual_tagging", "product_detection", "caption_generation"],
                warnings=plan.warnings,
                durations={"plan_seconds": round(perf_counter() - started, 3)},
                paths={
                    "video": video_path,
                    "plan": str(plan_path),
                    "visual_tag_report": str(visual_tag_report_path),
                    "product_detection_report": str(product_detection_path),
                    "caption_generation_log": str(caption_log_path),
                },
            ),
        )
        if plan.generate_voiceover and plan.voiceover_script:
            self.last_voiceover_subtitle_path = self._write_voiceover_subtitle(plan, target_dir)
        _progress(progress_callback, "plan_completed", 100)
        return plan

    def regenerate_captions(
        self,
        plan: SilentReupPlan,
        *,
        output_dir: str,
        industry: str,
        tone: str,
        strategy: str | None = None,
        product_context: dict | None = None,
        use_visual_tags: bool = True,
        respect_user_tag_overrides: bool = True,
    ) -> SilentReupPlan:
        target_dir = ensure_dir(output_dir)
        previous_texts = [caption.text for caption in plan.captions]
        next_strategy = strategy or plan.strategy
        effective_industry = (
            plan.visual_tagging.recommended_industry
            if industry == "auto"
            else industry
        )
        context = merge_product_detection_context({**(product_context or {}), "industry": effective_industry}, plan.product_detection)
        captions = self.caption_generator.generate_captions(
            video_path=plan.video_path,
            segments=plan.visual_segments,
            strategy=next_strategy,
            product_context=context,
            industry=industry,
            tone=tone,
            recent_caption_texts=[*self.recent_caption_texts, *previous_texts],
            video_recommended_industry=plan.visual_tagging.recommended_industry,
            use_visual_tags=use_visual_tags,
        )
        scores = [caption.quality_score for caption in captions if caption.quality_score is not None]
        metadata = plan.caption_generation.model_copy(
            update={
                "industry": normalize_silent_industry(context),
                "tone": tone,
                "strategy": next_strategy,
                "template_count_available": len(
                    self.caption_generator.template_service.list_templates(
                        industry=industry,
                        strategy=next_strategy,
                    )
                ),
                "captions_generated": len(captions),
                "regeneration_count": plan.caption_generation.regeneration_count + 1,
                "average_quality_score": round(sum(scores) / len(scores), 4) if scores else 1.0,
                "warnings": [
                    f"Caption {caption.index} cần review quality."
                    for caption in captions
                    if caption.quality_needs_review
                ],
            }
        )
        regenerated = plan.model_copy(
            update={
                "strategy": next_strategy,
                "captions": captions,
                "caption_generation": metadata,
            }
        )
        plan_path = target_dir / "silent_reup_plan.json"
        write_json(plan_path, regenerated.model_dump(mode="json"))
        self.last_plan_path = str(plan_path)
        self.write_caption_srt(regenerated, str(target_dir))
        self.recent_caption_texts.extend(caption.text for caption in captions)
        self.recent_caption_texts = self.recent_caption_texts[-80:]
        return regenerated

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
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        tts_settings: TTSSettings | None = None,
    ) -> SilentReupResult:
        target_dir = ensure_dir(output_dir)
        warnings = list(plan.warnings)
        errors: list[str] = []
        plan_path = target_dir / "silent_reup_plan.json"
        write_json(plan_path, plan.model_dump(mode="json"))
        self.last_plan_path = str(plan_path)
        _progress(progress_callback, "caption_export", 5)
        caption_srt = self.write_caption_srt(plan, str(target_dir), "silent_reup_caption_vi.srt")
        voiceover_path = None
        try:
            if plan.generate_voiceover and plan.voiceover_script:
                _progress(progress_callback, "voiceover", 20)
                if not self.last_voiceover_script_path:
                    script_path = target_dir / f"{Path(plan.video_path).stem}_voiceover_script.txt"
                    script_path.write_text(plan.voiceover_script, encoding="utf-8")
                    self.last_voiceover_script_path = str(script_path)
                self.last_voiceover_subtitle_path = self._write_voiceover_subtitle(plan, target_dir)
                voiceover_path = self._generate_voiceover(plan, settings, str(target_dir), tts_settings=tts_settings)
                warnings.extend(self.voice_generator.warnings)

            _progress(progress_callback, "video_probe", 40)
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
            _progress(progress_callback, "ffmpeg_render", 50)
            render_kwargs: dict[str, Any] = {
                "video": video,
                "subtitle_srt_path": caption_srt,
                "settings": render_settings,
                "output_dir": str(target_dir),
                "output_name": f"{Path(plan.video_path).stem}_silent_reup.mp4",
                "warnings": warnings,
                "voiceover_path": voiceover_path,
            }
            if "tts_settings" in inspect.signature(self.render_pipeline.render_video_with_srt).parameters:
                render_kwargs["tts_settings"] = tts_settings
            render_payload = self.render_pipeline.render_video_with_srt(**render_kwargs)
            result = SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=render_payload.get("path"),
                plan_path=self.last_plan_path,
                caption_srt_path=caption_srt,
                caption_ass_path=render_payload.get("subtitle_ass_file"),
                overlay_path=render_payload.get("overlay_file"),
                voiceover_path=voiceover_path,
                voiceover_subtitle_path=self.last_voiceover_subtitle_path,
                bgm_path=render_payload.get("bgm_file"),
                status="success",
                warnings=_dedupe(render_payload.get("warnings") or warnings),
                errors=_dedupe(render_payload.get("errors") or []),
            )
            _progress(progress_callback, "render_completed", 100)
        except Exception as exc:
            errors.append(str(exc))
            result = SilentReupResult(
                input_video_path=plan.video_path,
                output_video_path=None,
                plan_path=self.last_plan_path,
                caption_srt_path=caption_srt,
                caption_ass_path=None,
                overlay_path=None,
                voiceover_path=voiceover_path,
                voiceover_subtitle_path=self.last_voiceover_subtitle_path,
                bgm_path=None,
                status="failed",
                warnings=_dedupe(warnings),
                errors=_dedupe(errors),
            )

        log_path = target_dir / "silent_reup_log.json"
        result = result.model_copy(update={"log_path": str(log_path)})
        write_json(
            log_path,
            _standard_silent_log(
                settings=settings,
                industry=plan.caption_generation.industry,
                status=result.status,
                steps=["caption_export", "voiceover", "render"],
                failed_step="render" if result.status == "failed" else None,
                warnings=result.warnings,
                errors=result.errors,
                paths=result.model_dump(mode="json"),
            ),
        )
        return result

    def render_review_document(
        self,
        document: SubtitleReviewDocument,
        settings: DouyinReupSettings,
        output_dir: str,
        tts_settings: TTSSettings | None = None,
    ) -> dict:
        target_dir = ensure_dir(output_dir)
        context = document.context or {}
        base_plan = self._load_review_plan(document)
        captions = [
            ImmersiveCaptionLine(
                index=line.index,
                start=line.start_ms / 1000.0,
                end=line.end_ms / 1000.0,
                text=line.edited_text or line.translated_text,
                source="manual" if line.edited_text else _review_caption_source(document.source_type),
            )
            for line in document.lines
            if (line.edited_text or line.translated_text or "").strip()
        ]
        plan = base_plan.model_copy(
            update={
                "captions": captions,
                "generate_voiceover": settings.generate_voiceover_for_silent_video,
                "voiceover_script": None,
            }
        )
        voiceover_path = None
        review_product_context = merge_product_detection_context(
            context.get("product_context") if isinstance(context.get("product_context"), dict) else None,
            plan.product_detection,
        )
        if settings.generate_voiceover_for_silent_video:
            script = self.script_generator.generate_voiceover_script(
                plan,
                product_context=review_product_context,
                style=settings.visual_caption_style,
            )
            plan = plan.model_copy(update={"voiceover_script": script})
            script_path = target_dir / f"{Path(document.video_path).stem}_voiceover_script.txt"
            script_path.write_text(script, encoding="utf-8")
            self.last_voiceover_script_path = str(script_path)
            self.last_voiceover_subtitle_path = self._write_voiceover_subtitle(plan, target_dir)
            voiceover_path = self._generate_voiceover(plan, settings, str(target_dir), tts_settings=tts_settings)

        plan_path = target_dir / "silent_reup_plan.json"
        write_json(plan_path, plan.model_dump(mode="json"))
        self.last_plan_path = str(plan_path)
        render_settings = _render_settings_for_silent(settings)
        render_kwargs: dict[str, Any] = {
            "document_id": document.id,
            "settings": render_settings,
            "output_dir": str(target_dir),
            "voiceover_path": voiceover_path,
        }
        if "tts_settings" in inspect.signature(self.render_pipeline.render_from_review_document).parameters:
            render_kwargs["tts_settings"] = tts_settings
        result = self.render_pipeline.render_from_review_document(**render_kwargs)
        result.update(
            {
                "reup_mode": "silent_immersive",
                "silent_strategy": plan.strategy,
                "speech_score": plan.speech_score,
                "caption_source": _review_caption_source(document.source_type),
                "silent_plan_file": str(plan_path),
                "voiceover_file": voiceover_path,
                "voiceover_script_file": self.last_voiceover_script_path,
                "voiceover_subtitle_file": self.last_voiceover_subtitle_path,
                "product_detection": plan.product_detection.model_dump(mode="json") if plan.product_detection else None,
            }
        )
        write_json(
            target_dir / "silent_reup_log.json",
            _standard_silent_log(
                settings=settings,
                industry=plan.caption_generation.industry,
                status=str(result.get("status") or "success"),
                steps=["subtitle_review", "corrected_caption", "voiceover", "render"],
                failed_step=result.get("failed_step"),
                warnings=result.get("warnings") or [],
                errors=result.get("errors") or [],
                paths=result,
            ),
        )
        return result

    def _try_ocr_translate(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        target_dir: Path,
        warnings: list[str],
        gemini_api_keys: list[str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> str | None:
        if not settings.use_ocr_if_no_subtitle:
            return None
        try:
            if settings.ocr_subprocess_isolation:
                payload = run_in_isolated_process(
                    _silent_ocr_worker,
                    video_path,
                    str(target_dir / "ocr"),
                    settings.model_dump(mode="json"),
                    timeout_seconds=settings.ocr_timeout_seconds,
                    stage_name=f"OCR silent {Path(video_path).name}",
                )
                ocr_result = HardSubOCRResult.model_validate(payload)
            elif progress_callback is None:
                ocr_result = self.ocr_service.extract_hardsub_to_srt(video_path, str(target_dir / "ocr"), settings)
            else:
                ocr_result = self.ocr_service.extract_hardsub_to_srt(
                    video_path,
                    str(target_dir / "ocr"),
                    settings,
                    progress_callback=progress_callback,
                )
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
        try:
            translation = self.translator.translate_srt(
                ocr_result.source_srt_path,
                str(translated_path),
                source_language=settings.source_language,
                target_language=settings.target_language,
                provider=settings.translation_provider,
                api_keys=gemini_api_keys or [],
            )
        except Exception as exc:
            raise RuntimeError(
                "OCR đã nhận diện được chữ trong video nhưng không dịch được sang tiếng Việt. "
                "Hãy kiểm tra Gemini API key/quota hoặc tắt OCR hard-sub nếu muốn dùng caption template."
            ) from exc
        warnings.extend(translation.warnings)
        self.last_ocr_translated_srt_path = translation.translated_srt_path
        return translation.translated_srt_path

    def _attach_ocr_text_to_segments(self, segments: list[SilentVisualSegment]) -> list[SilentVisualSegment]:
        if not segments or not self.last_ocr_source_srt_path:
            return segments
        try:
            blocks = parse_srt_blocks(self.last_ocr_source_srt_path)
        except (OSError, ValueError):
            return segments
        enriched = []
        for segment in segments:
            texts = [
                block.text
                for block in blocks
                if min(segment.end, block.end) > max(segment.start, block.start)
            ]
            enriched.append(
                segment.model_copy(
                    update={
                        "ocr_text": " ".join(texts).strip() or None,
                        "ocr_confidence": self.last_ocr_average_confidence if texts else None,
                    }
                )
            )
        return enriched

    def _load_review_plan(self, document: SubtitleReviewDocument) -> SilentReupPlan:
        context = document.context or {}
        candidates = [
            context.get("silent_plan_file"),
            str(Path(document.translated_srt_path).parent / "silent_reup_plan.json"),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return SilentReupPlan.model_validate_json(Path(str(candidate)).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        return SilentReupPlan(
            video_path=document.video_path,
            strategy=str(context.get("silent_strategy") or "chill_immersive"),
            has_speech=bool(context.get("has_speech", False)),
            speech_score=float(context.get("speech_score") or 0.0),
            visual_segments=[],
            captions=[],
            generate_voiceover=False,
            recommended_audio_mode=str(context.get("recommended_audio_mode") or "original_audio_plus_bgm"),
            warnings=[],
        )

    def _write_voiceover_subtitle(self, plan: SilentReupPlan, target_dir: Path) -> str:
        script = plan.voiceover_script or ""
        sentences = [part.strip() for part in script.replace("!", ".").replace("?", ".").split(".") if part.strip()]
        if not sentences:
            sentences = [caption.text for caption in plan.captions if caption.text.strip()]
        duration = _plan_duration(plan)
        count = max(1, len(sentences))
        blocks = [
            SubtitleBlock(
                index=index,
                start=duration * ((index - 1) / count),
                end=duration * (index / count),
                text=sentence,
            )
            for index, sentence in enumerate(sentences, start=1)
        ]
        path = target_dir / f"{Path(plan.video_path).stem}_voiceover_sub.srt"
        write_srt_blocks(blocks, str(path))
        return str(path)

    def _generate_voiceover(
        self,
        plan: SilentReupPlan,
        settings: DouyinReupSettings,
        output_dir: str,
        tts_settings: TTSSettings | None = None,
    ) -> str:
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
        merged_tts_settings = voiceover_tts_settings(
            tts_settings,
            provider=settings.silent_voiceover_provider,
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
            tts_settings=merged_tts_settings,
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


def _progress(
    callback: Callable[[dict[str, Any]], None] | None,
    step: str,
    progress: int,
) -> None:
    if callback:
        callback({"current_step": step, "progress": max(0, min(100, int(progress)))})


def _mapped_progress_callback(
    callback: Callable[[dict[str, Any]], None] | None,
    start: int,
    end: int,
    prefix: str,
) -> Callable[[dict[str, Any]], None] | None:
    if callback is None:
        return None

    def mapped(payload: dict[str, Any]) -> None:
        source_progress = max(0, min(100, int(payload.get("progress", 0))))
        step = str(payload.get("current_step") or "processing")
        callback(
            {
                **payload,
                "current_step": f"{prefix}_{step}",
                "progress": start + int((source_progress / 100) * max(0, end - start)),
            }
        )

    return mapped


def _standard_silent_log(
    *,
    settings: DouyinReupSettings,
    industry: str,
    status: str,
    steps: list[str],
    failed_step: str | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    durations: dict | None = None,
    paths: dict | None = None,
) -> dict:
    return {
        "version": APP_VERSION,
        "mode": "silent_immersive",
        "preset_id": settings.preset_id,
        "strategy": settings.silent_mode_strategy,
        "industry": industry,
        "status": status,
        "steps": steps,
        "failed_step": failed_step,
        "warnings": _dedupe(warnings or []),
        "errors": _dedupe(errors or []),
        "durations": durations or {},
        "paths": paths or {},
    }


def _review_caption_source(source_type: str | None) -> str:
    if source_type in {"ocr_translation", "visual_generated", "template", "manual"}:
        return source_type
    return "manual"


def normalize_silent_industry(product_context: dict | None) -> str:
    from app.modules.silent_caption_templates.caption_template_service import normalize_industry

    context = product_context or {}
    return normalize_industry(context.get("industry") or context.get("category"))


def _silent_ocr_worker(video_path: str, output_dir: str, settings_payload: dict[str, Any]) -> dict[str, Any]:
    settings = DouyinReupSettings.model_validate(settings_payload)
    result = HardSubOCRService().extract_hardsub_to_srt(video_path, output_dir, settings, progress_callback=None)
    return result.model_dump(mode="json")
