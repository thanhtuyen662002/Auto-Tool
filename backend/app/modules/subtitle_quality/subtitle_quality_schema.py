from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubtitleQualitySeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class SubtitleQualityIssueType(str, Enum):
    too_long = "too_long"
    too_many_lines = "too_many_lines"
    duration_too_short = "duration_too_short"
    reading_speed_too_high = "reading_speed_too_high"
    empty_translation = "empty_translation"
    untranslated_chinese = "untranslated_chinese"
    suspicious_symbols = "suspicious_symbols"
    markdown_or_json_leak = "markdown_or_json_leak"
    ocr_low_confidence = "ocr_low_confidence"
    asr_low_confidence = "asr_low_confidence"
    source_target_mismatch = "source_target_mismatch"
    possible_literal_translation = "possible_literal_translation"
    repeated_text = "repeated_text"
    timestamp_overlap = "timestamp_overlap"
    timestamp_out_of_range = "timestamp_out_of_range"


class SubtitleQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: SubtitleQualityIssueType
    severity: SubtitleQualitySeverity
    message: str
    suggestion: str | None = None


class SubtitleLineQualityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_index: int
    score: float = Field(ge=0, le=1)
    severity: SubtitleQualitySeverity
    needs_review: bool
    source_text: str | None = None
    translated_text: str
    edited_text: str | None = None
    duration_ms: int
    char_count: int
    line_count: int
    chars_per_second: float
    ocr_confidence: float | None = None
    asr_confidence: float | None = None
    issues: list[SubtitleQualityIssue] = Field(default_factory=list)


class SubtitleDocumentQualityReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: str
    video_id: str | None = None
    project_id: str | None = None
    average_score: float = Field(ge=0, le=1)
    total_lines: int
    needs_review_count: int
    critical_count: int
    warning_count: int
    lines: list[SubtitleLineQualityScore]
    summary_warnings: list[str] = Field(default_factory=list)
    issues_breakdown: dict[str, int] = Field(default_factory=dict)
    report_file: str | None = None
    created_at: str


class SubtitleQualityFlaggedLinesResponse(BaseModel):
    items: list[SubtitleLineQualityScore] = Field(default_factory=list)


class SubtitleRewriteSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str = "short_natural_vietnamese"


class SubtitleRewriteSuggestionResponse(BaseModel):
    suggestion: str
    source: str = "rule_based"
    issues: list[dict[str, Any]] = Field(default_factory=list)
