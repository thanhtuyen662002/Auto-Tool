from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SubtitleSourceType = Literal["sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub", "none"]


class DouyinReupSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    preset_id: str | None = None
    preset_name: str | None = None
    source_language: str = "zh"
    target_language: str = "vi"
    translation_style: str = "sat_nghia_troi_chay"
    subtitle_position: str = "bottom_overlay"
    translation_provider: str = "gemini"
    subtitle_source_priority: list[str] = Field(
        default_factory=lambda: ["sidecar_srt", "embedded_subtitle", "ocr_hardsub", "asr"]
    )
    use_sidecar_srt: bool = True
    use_embedded_subtitle: bool = True
    use_asr_if_no_subtitle: bool = True
    asr_provider: str = "faster_whisper"
    asr_model_size: str = "base"
    asr_device: str = "auto"
    asr_vad_filter: bool = True
    asr_max_audio_seconds: int = Field(default=180, ge=0, le=7200)
    asr_subprocess_isolation: bool = False
    asr_timeout_seconds: int = Field(default=1200, ge=60, le=24 * 60 * 60)
    asr_subtitle_offset_seconds: float = Field(default=-0.25, ge=-2.0, le=2.0)
    use_ocr_if_asr_failed: bool = True
    use_ocr_if_no_subtitle: bool = True
    ocr_provider: str = "easyocr"
    ocr_language: str = "ch"
    ocr_sample_fps: float = Field(default=2.0, gt=0, le=10)
    ocr_subprocess_isolation: bool = False
    ocr_timeout_seconds: int = Field(default=1200, ge=60, le=24 * 60 * 60)
    ocr_region_mode: str = "full_frame"
    ocr_manual_region: dict | None = None
    ocr_min_confidence: float = Field(default=0.35, ge=0, le=1)
    ocr_dedupe_similarity: float = Field(default=0.86, ge=0, le=1)
    ocr_min_text_length: int = Field(default=2, ge=1, le=50)
    ocr_merge_gap_ms: int = Field(default=600, ge=0, le=10_000)
    ocr_min_duration_ms: int = Field(default=500, ge=100, le=10_000)
    ocr_max_duration_ms: int = Field(default=6000, ge=500, le=30_000)
    ocr_filter_watermarks: bool = True
    ocr_watermark_terms: list[str] = Field(default_factory=lambda: ["\u5c0f\u7c73\u540c\u5b66", "\u5c0f\u7c73\u540c\u5b78"])
    subtitle_quality_gate_enabled: bool = True
    asr_quality_min_blocks: int = Field(default=3, ge=1, le=20)
    asr_quality_min_chars: int = Field(default=24, ge=1, le=500)
    ocr_quality_min_blocks: int = Field(default=2, ge=1, le=20)
    ocr_quality_min_chars: int = Field(default=16, ge=1, le=500)
    subtitle_quality_min_coverage: float = Field(default=0.18, ge=0, le=1)
    prefer_ocr_over_asr_when_text_visible: bool = False
    visual_style_preset_id: str = "clean_review_light"
    burn_subtitle: bool = True
    add_overlay: bool = False
    overlay_mode: Literal["preset", "none", "custom"] = "none"
    custom_overlay_path: str | None = None
    custom_overlay_height_percent: int | None = Field(default=100, ge=5, le=100)
    custom_overlay_fit_mode: Literal["cover", "contain", "stretch"] = "cover"
    subtitle_style_custom_enabled: bool = False
    subtitle_font_family: str = "Arial"
    subtitle_font_size: int = Field(default=54, ge=18, le=120)
    subtitle_font_color: str = "#FFFFFF"
    subtitle_stroke_color: str = "#000000"
    subtitle_stroke_width: int = Field(default=2, ge=0, le=12)
    subtitle_shadow_enabled: bool = True
    subtitle_shadow_color: str = "#000000"
    subtitle_shadow_opacity: float = Field(default=0.35, ge=0, le=1)
    subtitle_shadow_size: int = Field(default=2, ge=0, le=12)
    subtitle_max_chars_per_line: int = Field(default=22, ge=10, le=48)
    subtitle_max_lines: int = Field(default=2, ge=1, le=3)
    subtitle_cover_enabled: bool = True
    subtitle_cover_mode: Literal["solid", "blur"] = "solid"
    subtitle_cover_blur_strength: int = Field(default=12, ge=2, le=30)
    subtitle_cover_color: str = "#000000"
    subtitle_cover_opacity: float = Field(default=0.86, ge=0, le=1)
    subtitle_cover_auto_position: bool = True
    subtitle_cover_probe_if_no_ocr: bool = True
    subtitle_cover_probe_sample_fps: float = Field(default=1.0, gt=0, le=2.0)
    subtitle_cover_height_ratio: float = Field(default=0.12, ge=0.05, le=0.45)
    subtitle_cover_bottom_ratio: float = Field(default=0.0, ge=0, le=0.35)
    subtitle_cover_padding_ratio: float = Field(default=0.035, ge=0, le=0.12)
    subtitle_cover_lead_seconds: float = Field(default=0.85, ge=0, le=3.0)
    subtitle_cover_tail_seconds: float = Field(default=0.25, ge=0, le=3.0)
    subtitle_cover_radius_ratio: float = Field(default=0.035, ge=0, le=0.12)
    subtitle_cover_text_y_offset_ratio: float = Field(default=0.0, ge=-0.2, le=0.2)
    subtitle_cover_only_if_chinese_detected: bool = True
    subtitle_cover_ai_fallback_enabled: bool = True
    keep_original_audio: bool = True
    add_bgm: bool = True
    music_folder: str | None = None
    favorite_music_paths: list[str] = Field(default_factory=list)
    bgm_volume: float = Field(default=0.16, ge=0, le=1)
    original_audio_volume: float = Field(default=0.85, ge=0, le=1)
    reduce_original_voice: bool = False
    original_voice_reduction_strength: float = Field(default=0.65, ge=0, le=1)
    original_voice_reduction_fallback_volume: float = Field(default=0.35, ge=0, le=1)
    duck_bgm_when_voice: bool = False
    resolution: str = "1080x1920"
    video_dimension_mode: Literal["vertical", "horizontal", "square", "auto"] = "vertical"
    fps: int = Field(default=30, gt=0, le=120)
    process_mode: str = "all"
    max_videos: int | None = Field(default=None, gt=0)
    selected_video_paths: list[str] = Field(default_factory=list)
    source_selection_id: str | None = None
    batch_performance_mode: Literal["safe", "balanced", "fast"] = "safe"
    batch_chunk_size: int = Field(default=50, ge=1, le=500)
    batch_ffmpeg_timeout_seconds: int = Field(default=900, ge=60, le=24 * 60 * 60)
    batch_item_timeout_seconds: int = Field(default=1800, ge=60, le=24 * 60 * 60)
    batch_watchdog_stale_minutes: int = Field(default=20, ge=1, le=24 * 60)
    batch_pause_on_repeated_failures: bool = True
    batch_max_consecutive_failures: int = Field(default=10, ge=1, le=1000)
    keep_temp: bool = False
    review_subtitles_before_render: bool = True
    auto_render_after_translation: bool = False
    auto_mark_low_quality_lines: bool = True
    enable_subtitle_rewrite_suggestions: bool = True
    auto_generate_rewrite_for_flagged_lines: bool = False
    auto_apply_safe_rewrites: bool = False
    default_rewrite_style: str = "short_natural"
    enable_silent_immersive_mode: bool = True
    silent_mode_detection: bool = True
    silent_mode_strategy: Literal["chill_immersive", "product_review_voiceover", "sales_recut"] = "chill_immersive"
    detect_speech_presence: bool = True
    speech_detection_threshold: float = Field(default=0.35, ge=0, le=1)
    auto_route_speech_to_voice_reup: bool = True
    auto_route_no_speech_to_silent_reup: bool = True
    auto_route_speech_threshold: float = Field(default=0.28, ge=0, le=1)
    use_visual_segments_for_silent_video: bool = True
    silent_segment_duration_min: float = Field(default=1.2, gt=0, le=30)
    silent_segment_duration_max: float = Field(default=4.0, gt=0, le=60)
    generate_visual_captions: bool = False
    silent_visual_caption_min_product_confidence: float = Field(default=0.75, ge=0, le=1)
    silent_visual_caption_min_segments: int = Field(default=3, ge=1, le=20)
    silent_voiceover_max_duration_ratio: float = Field(default=0.85, ge=0.2, le=1.2)
    visual_caption_language: str = "vi"
    visual_caption_style: str = "natural_short"
    silent_caption_tone: Literal["natural", "cute", "clean_review", "sales_light", "chill"] = "natural"
    generate_voiceover_for_silent_video: bool = False
    silent_voiceover_provider: str = "edge_tts"
    silent_voiceover_voice: str = "vi-VN-HoaiMyNeural"
    voiceover_auto_slow_video: bool = True
    voiceover_max_video_slowdown: float = Field(default=1.28, ge=1.0, le=1.5)
    voiceover_comfort_speedup: float = Field(default=1.18, ge=1.0, le=3.0)
    keep_immersive_original_audio: bool = True
    immersive_original_audio_volume: float = Field(default=0.75, ge=0, le=1)
    add_bgm_for_silent_video: bool = True
    immersive_bgm_volume: float = Field(default=0.18, ge=0, le=1)
    silent_review_before_render: bool = True
    product_context_lock_enabled: bool = True
    locked_product_name: str | None = None
    locked_industry: str | None = None
    locked_product_keywords: list[str] = Field(default_factory=list)

    # Cấu hình độc lập cho video dài / phim
    long_video_mode: Literal["viet_sub", "dubbing"] = "viet_sub"
    isolate_ambient_sound: bool = True
    multi_speaker_enabled: bool = False
    speaker_voice_mapping: dict[str, str] = Field(default_factory=dict)


    @field_validator(
        "source_language",
        "target_language",
        "translation_provider",
        "asr_provider",
        "asr_model_size",
        "asr_device",
        "ocr_provider",
        "ocr_language",
        "ocr_region_mode",
        "visual_style_preset_id",
        "process_mode",
        "translation_style",
        "subtitle_position",
        "default_rewrite_style",
        "silent_mode_strategy",
        "visual_caption_language",
        "visual_caption_style",
        "silent_caption_tone",
        "silent_voiceover_provider",
        "silent_voiceover_voice",
        "batch_performance_mode",
    )
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Không được để trống.")
        return cleaned

    @field_validator("custom_overlay_path")
    @classmethod
    def clean_custom_overlay_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator(
        "subtitle_font_color",
        "subtitle_stroke_color",
        "subtitle_shadow_color",
        "subtitle_cover_color",
    )
    @classmethod
    def clean_hex_color(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("#"):
            cleaned = f"#{cleaned}"
        if len(cleaned) != 7:
            raise ValueError(f"Màu phải dùng định dạng #RRGGBB: {value}")
        try:
            int(cleaned[1:], 16)
        except ValueError as exc:
            raise ValueError(f"Màu phải dùng định dạng #RRGGBB: {value}") from exc
        return cleaned.upper()

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise ValueError("resolution phải dùng định dạng WIDTHxHEIGHT, ví dụ 1080x1920.")
        try:
            width, height = (int(part) for part in parts)
        except ValueError as exc:
            raise ValueError("resolution width/height phải là số nguyên.") from exc
        if width <= 0 or height <= 0:
            raise ValueError("resolution width/height phải lớn hơn 0.")
        return f"{width}x{height}"

    @field_validator("subtitle_source_priority")
    @classmethod
    def clean_priority(cls, value: list[str]) -> list[str]:
        allowed = {"sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub"}
        cleaned: list[str] = []
        for item in value:
            source = item.strip().lower()
            if source not in allowed:
                raise ValueError(f"subtitle_source_priority không hỗ trợ: {item}")
            if source not in cleaned:
                cleaned.append(source)
        return cleaned or ["sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub"]

    @field_validator("ocr_region_mode")
    @classmethod
    def validate_ocr_region_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        allowed = {"bottom_auto", "middle_lower", "full_frame", "manual"}
        if cleaned not in allowed:
            raise ValueError(f"ocr_region_mode phải là một trong: {', '.join(sorted(allowed))}")
        return cleaned

    @field_validator("ocr_watermark_terms")
    @classmethod
    def clean_ocr_watermark_terms(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item or "").split())
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    @field_validator("default_rewrite_style")
    @classmethod
    def validate_rewrite_style(cls, value: str) -> str:
        cleaned = value.strip().lower()
        allowed = {"short_natural", "very_short", "casual_tiktok", "clear_review", "sales_natural"}
        if cleaned not in allowed:
            raise ValueError(f"default_rewrite_style must be one of: {', '.join(sorted(allowed))}")
        return cleaned

    @field_validator("process_mode")
    @classmethod
    def validate_process_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        allowed = {"all", "selected", "first_n"}
        if cleaned not in allowed:
            raise ValueError(f"process_mode phải là một trong: {', '.join(sorted(allowed))}")
        return cleaned

    @field_validator("selected_video_paths")
    @classmethod
    def clean_selected_paths(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            path = str(item).strip()
            if not path or path in seen:
                continue
            cleaned.append(path)
            seen.add(path)
        return cleaned

    @field_validator("favorite_music_paths")
    @classmethod
    def clean_favorite_music_paths(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            path = str(item).strip()
            if not path or path in seen:
                continue
            cleaned.append(path)
            seen.add(path)
        return cleaned

    @field_validator("locked_product_name", "locked_industry")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("locked_product_keywords")
    @classmethod
    def clean_locked_product_keywords(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item).split()).strip()
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned

    @field_validator("source_selection_id")
    @classmethod
    def clean_source_selection_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_silent_segment_duration(self) -> "DouyinReupSettings":
        if self.silent_segment_duration_min > self.silent_segment_duration_max:
            raise ValueError("silent_segment_duration_min must be less than or equal to silent_segment_duration_max.")
        return self


class DouyinVideoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    filename: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    sidecar_srt_path: str | None = None
    embedded_subtitle_found: bool = False
    status: str = "valid"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SubtitleSourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_path: str
    source_type: SubtitleSourceType
    source_srt_path: str | None = None
    language: str = "zh"
    ocr_debug_json_path: str | None = None
    ocr_frame_count: int = 0
    ocr_detected_line_count: int = 0
    ocr_average_confidence: float = 0.0
    ocr_region_mode: str | None = None
    subtitle_quality_score: float = 0.0
    subtitle_quality_reasons: list[str] = Field(default_factory=list)
    subtitle_quality_stats: dict[str, Any] = Field(default_factory=dict)
    subtitle_rejected_sources: list[dict[str, Any]] = Field(default_factory=list)
    fallback_mode: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_srt_path: str
    translated_srt_path: str
    translated_ass_path: str | None = None
    provider: str = "fallback"
    source_language: str = "zh"
    target_language: str = "vi"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DouyinOutputResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    index: int
    path: str
    status: str
    source_video: str
    preset_id: str | None = None
    preset_name: str | None = None
    subtitle_source: str | None = None
    source_srt_file: str | None = None
    translated_srt_file: str | None = None
    corrected_srt_file: str | None = None
    subtitle_ass_file: str | None = None
    overlay_file: str | None = None
    bgm_file: str | None = None
    log_file: str | None = None
    subtitle_review_document_id: str | None = None
    reup_mode: str | None = None
    silent_strategy: str | None = None
    speech_score: float | None = None
    caption_source: str | None = None
    silent_plan_file: str | None = None
    silent_caption_generation: dict[str, Any] | None = None
    silent_visual_tagging: dict[str, Any] | None = None
    product_detection: dict[str, Any] | None = None
    voiceover_file: str | None = None
    voiceover_script_file: str | None = None
    voiceover_subtitle_file: str | None = None
    ocr_debug_json_path: str | None = None
    ocr_frame_count: int = 0
    ocr_detected_line_count: int = 0
    ocr_average_confidence: float = 0.0
    ocr_provider: str | None = None
    ocr_region_mode: str | None = None
    subtitle_quality_score: float = 0.0
    subtitle_quality_reasons: list[str] = Field(default_factory=list)
    subtitle_quality_stats: dict[str, Any] = Field(default_factory=dict)
    subtitle_rejected_sources: list[dict[str, Any]] = Field(default_factory=list)
    fallback_mode: str | None = None
    failed_step: str | None = None
    error_message: str | None = None
    can_retry: bool = False
    duration: float | None = None
    durations: dict[str, float] = Field(default_factory=dict)
    retry_history: list[dict[str, str | None]] = Field(default_factory=list)
    final_output_qa: dict | None = None
    publish_manifest_file: str | None = None
    cleanup_report: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DouyinReupSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_name: str
    output_folder: str
    total_videos: int
    processed_outputs: int
    successful_outputs: int
    failed_outputs: int
    warnings_count: int = 0
    subtitle_sources: dict[str, int] = Field(default_factory=dict)
    failed_items: list[dict[str, str | int]] = Field(default_factory=list)
    outputs: list[DouyinOutputResult] = Field(default_factory=list)
    subtitle_review: dict[str, int | bool] = Field(default_factory=dict)
    silent_immersive: dict[str, Any] = Field(default_factory=dict)
    summary_file: str | None = None
