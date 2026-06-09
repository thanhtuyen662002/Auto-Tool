from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SubtitleSourceType = Literal["sidecar_srt", "embedded_subtitle", "asr", "none"]


class DouyinReupSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    source_language: str = "zh"
    target_language: str = "vi"
    translation_provider: str = "gemini"
    subtitle_source_priority: list[str] = Field(
        default_factory=lambda: ["sidecar_srt", "embedded_subtitle", "asr"]
    )
    use_sidecar_srt: bool = True
    use_embedded_subtitle: bool = True
    use_asr_if_no_subtitle: bool = True
    asr_provider: str = "faster_whisper"
    asr_model_size: str = "medium"
    asr_device: str = "auto"
    asr_vad_filter: bool = False
    asr_subtitle_offset_seconds: float = Field(default=-0.25, ge=-2.0, le=2.0)
    visual_style_preset_id: str = "clean_review_light"
    burn_subtitle: bool = True
    add_overlay: bool = True
    music_folder: str | None = None
    bgm_volume: float = Field(default=0.16, ge=0, le=1)
    original_audio_volume: float = Field(default=0.85, ge=0, le=1)
    duck_bgm_when_voice: bool = False
    resolution: str = "1080x1920"
    fps: int = Field(default=30, gt=0, le=120)
    process_mode: str = "all"
    max_videos: int | None = Field(default=None, gt=0)
    selected_video_paths: list[str] = Field(default_factory=list)
    keep_temp: bool = False

    @field_validator(
        "source_language",
        "target_language",
        "translation_provider",
        "asr_provider",
        "asr_model_size",
        "asr_device",
        "visual_style_preset_id",
        "process_mode",
    )
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Không được để trống.")
        return cleaned

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
        allowed = {"sidecar_srt", "embedded_subtitle", "asr"}
        cleaned: list[str] = []
        for item in value:
            source = item.strip().lower()
            if source not in allowed:
                raise ValueError(f"subtitle_source_priority không hỗ trợ: {item}")
            if source not in cleaned:
                cleaned.append(source)
        return cleaned or ["sidecar_srt", "embedded_subtitle", "asr"]

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
    subtitle_source: str | None = None
    source_srt_file: str | None = None
    translated_srt_file: str | None = None
    subtitle_ass_file: str | None = None
    overlay_file: str | None = None
    bgm_file: str | None = None
    log_file: str | None = None
    duration: float | None = None
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
    summary_file: str | None = None
