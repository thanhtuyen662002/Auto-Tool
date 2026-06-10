from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlatformTarget(str, Enum):
    tiktok = "tiktok"
    instagram_reels = "instagram_reels"
    youtube_shorts = "youtube_shorts"
    generic_vertical = "generic_vertical"


class QASeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class FinalOutputQAIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: str
    severity: QASeverity
    message: str
    suggestion: str | None = None


class VideoProbeInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    readable: bool
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_audio: bool = False
    bitrate: int | None = None
    file_size_mb: float | None = None
    error: str | None = None


class AudioQualityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    has_audio: bool
    peak_db: float | None = None
    mean_volume_db: float | None = None
    max_volume_db: float | None = None
    warnings: list[str] = Field(default_factory=list)


class SubtitleVisibilityInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subtitle_expected: bool = True
    subtitle_file_path: str | None = None
    overlay_file_path: str | None = None
    estimated_subtitle_zone: dict | None = None
    safe_zone_ok: bool = True
    warnings: list[str] = Field(default_factory=list)


class FinalOutputQAReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str | None = None
    project_id: str | None = None
    video_id: str | None = None
    platform_target: PlatformTarget = PlatformTarget.generic_vertical
    output_video_path: str
    probe: VideoProbeInfo
    audio: AudioQualityInfo | None = None
    subtitle_visibility: SubtitleVisibilityInfo | None = None
    score: float = Field(ge=0, le=1)
    status: Literal["passed", "passed_with_warnings", "failed"]
    issues: list[FinalOutputQAIssue] = Field(default_factory=list)
    report_path: str | None = None
    created_at: str


class ExportPackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    path: str
    file_type: str
    exists: bool


class PlatformExportPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str | None = None
    project_id: str | None = None
    platform_target: PlatformTarget
    output_dir: str
    items: list[ExportPackItem] = Field(default_factory=list)
    caption_txt_path: str | None = None
    caption_csv_path: str | None = None
    posting_checklist_path: str | None = None
    qa_summary_path: str | None = None
    manifest_path: str | None = None
    created_at: str


class FinalOutputQACheckRequest(BaseModel):
    output_video_path: str
    platform_target: PlatformTarget = PlatformTarget.tiktok
    ass_path: str | None = None
    overlay_path: str | None = None
    subtitle_expected: bool = True
    audio_expected: bool = True


class FinalOutputQACheckResponse(BaseModel):
    success: bool = True
    report: FinalOutputQAReport


class FinalOutputQAJobRequest(BaseModel):
    platform_target: PlatformTarget = PlatformTarget.tiktok


class FinalOutputQAJobResponse(BaseModel):
    success: bool = True
    reports: list[FinalOutputQAReport] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)


class CreateExportPackRequest(BaseModel):
    platform_target: PlatformTarget = PlatformTarget.tiktok
    output_dir: str | None = None
    copy_videos: bool = True
    include_subtitles: bool = True
    include_logs: bool = True
    include_captions: bool = True
    include_posting_checklist: bool = True
    output_indexes: list[int] = Field(default_factory=list)


class PlatformExportPackResponse(BaseModel):
    success: bool = True
    export_pack: PlatformExportPack
