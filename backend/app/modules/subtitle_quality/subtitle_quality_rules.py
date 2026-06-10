from __future__ import annotations

import re

from app.modules.subtitle_quality.subtitle_quality_schema import (
    SubtitleQualityIssue,
    SubtitleQualityIssueType,
    SubtitleQualitySeverity,
)


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
MARKDOWN_OR_JSON_RE = re.compile(r"\x60\x60\x60|[{}\[\]]|\"translation\"\s*:|\bSRT\s*:", re.IGNORECASE)
SUSPICIOUS_SYMBOL_RE = re.compile(r"(#{3,}|\*{3,}|={3,}|~{3,}|�|ä¹±ç )")


def evaluate_line_quality(
    *,
    source_text: str | None,
    text: str,
    duration_ms: int,
    line_count: int,
    chars_per_second: float,
    next_start_ms: int | None = None,
    current_end_ms: int | None = None,
    video_duration_ms: int | None = None,
    ocr_confidence: float | None = None,
    asr_confidence: float | None = None,
    repeated_three_times: bool = False,
) -> list[SubtitleQualityIssue]:
    issues: list[SubtitleQualityIssue] = []
    stripped = text.strip()
    char_count = len(stripped.replace("\n", ""))

    if char_count > 76:
        issues.append(_issue("too_long", "critical", "Phụ đề quá dài, người xem có thể không đọc kịp.", "Rút gọn câu hoặc chia thành câu ngắn hơn."))
    elif char_count > 56:
        issues.append(_issue("too_long", "warning", "Phụ đề hơi dài, người xem có thể không đọc kịp.", "Rút gọn câu hoặc chia thành câu ngắn hơn."))

    if line_count > 3:
        issues.append(_issue("too_many_lines", "critical", "Phụ đề có quá nhiều dòng.", "Giữ tối đa 2 dòng nếu có thể."))
    elif line_count > 2:
        issues.append(_issue("too_many_lines", "warning", "Phụ đề nên tối đa 2 dòng.", "Chia lại hoặc rút gọn câu."))

    if chars_per_second > 24:
        issues.append(_issue("reading_speed_too_high", "critical", "Tốc độ đọc quá cao.", "Rút ngắn câu hoặc kéo dài thời lượng subtitle."))
    elif chars_per_second > 18:
        issues.append(_issue("reading_speed_too_high", "warning", "Tốc độ đọc hơi cao.", "Rút gọn câu để dễ đọc hơn."))

    if duration_ms < 450:
        issues.append(_issue("duration_too_short", "critical", "Thời lượng subtitle quá ngắn.", "Kiểm tra timing của dòng này."))
    elif duration_ms < 700:
        issues.append(_issue("duration_too_short", "warning", "Thời lượng subtitle hơi ngắn.", "Kiểm tra timing nếu người xem khó đọc."))

    if not stripped:
        issues.append(_issue("empty_translation", "critical", "Bản dịch đang rỗng.", "Bổ sung bản dịch tiếng Việt cho dòng này."))

    cjk_count = len(CJK_RE.findall(stripped))
    if cjk_count >= 3:
        issues.append(_issue("untranslated_chinese", "critical", "Bản dịch vẫn còn nhiều ký tự tiếng Trung.", "Dịch lại phần tiếng Trung còn sót."))
    elif cjk_count > 0:
        issues.append(_issue("untranslated_chinese", "warning", "Bản dịch còn ký tự tiếng Trung.", "Kiểm tra xem đây là tên riêng hay phần chưa dịch."))

    if MARKDOWN_OR_JSON_RE.search(stripped):
        issues.append(_issue("markdown_or_json_leak", "warning", "Subtitle có dấu hiệu lọt markdown hoặc JSON.", "Xóa phần markdown/JSON không thuộc nội dung thoại."))

    if SUSPICIOUS_SYMBOL_RE.search(stripped):
        issues.append(_issue("suspicious_symbols", "warning", "Subtitle có ký tự lạ hoặc lỗi mã hóa.", "Sửa ký tự lỗi trước khi approve."))

    if ocr_confidence is not None:
        if ocr_confidence < 0.40:
            issues.append(_issue("ocr_low_confidence", "critical", "OCR confidence thấp.", "Đối chiếu lại chữ trên video."))
        elif ocr_confidence < 0.55:
            issues.append(_issue("ocr_low_confidence", "warning", "OCR confidence hơi thấp.", "Kiểm tra lại dòng OCR này."))

    if asr_confidence is not None:
        if asr_confidence < 0.40:
            issues.append(_issue("asr_low_confidence", "critical", "ASR confidence thấp.", "Nghe lại audio ở đoạn này."))
        elif asr_confidence < 0.55:
            issues.append(_issue("asr_low_confidence", "warning", "ASR confidence hơi thấp.", "Kiểm tra lại phần nhận diện giọng nói."))

    source_len = len((source_text or "").strip())
    if source_len > 20 and char_count < 3:
        issues.append(_issue("source_target_mismatch", "critical", "Source dài nhưng bản dịch quá ngắn bất thường.", "Kiểm tra thiếu bản dịch."))
    elif 0 < source_len < 5 and char_count > 80:
        issues.append(_issue("source_target_mismatch", "warning", "Source ngắn nhưng bản dịch quá dài bất thường.", "Kiểm tra bản dịch có bị thêm ý không."))

    if source_text and stripped and _normalize_for_compare(source_text) == _normalize_for_compare(stripped):
        issues.append(_issue("possible_literal_translation", "warning", "Bản dịch giống hệt source.", "Kiểm tra dòng này có bị giữ nguyên không."))

    if repeated_three_times:
        issues.append(_issue("repeated_text", "warning", "Cùng một bản dịch lặp lại nhiều dòng liên tiếp.", "Kiểm tra lỗi lặp subtitle hoặc lỗi dịch."))

    if current_end_ms is not None and next_start_ms is not None and current_end_ms > next_start_ms:
        issues.append(_issue("timestamp_overlap", "warning", "Timestamp subtitle bị chồng lên dòng sau.", "Kiểm tra lại timing."))

    if video_duration_ms is not None and current_end_ms is not None and current_end_ms > video_duration_ms:
        issues.append(_issue("timestamp_out_of_range", "warning", "Subtitle vượt quá thời lượng video.", "Điều chỉnh end time của dòng này."))

    return issues


def _issue(issue_type: str, severity: str, message: str, suggestion: str | None = None) -> SubtitleQualityIssue:
    return SubtitleQualityIssue(
        issue_type=SubtitleQualityIssueType(issue_type),
        severity=SubtitleQualitySeverity(severity),
        message=message,
        suggestion=suggestion,
    )


def _normalize_for_compare(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()
