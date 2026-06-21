from __future__ import annotations

from app.modules.douyin_reup.subtitle_timing_guard import (
    SubtitleTimingGuard,
    format_srt_timestamp,
    parse_srt_blocks,
    split_text_for_display,
    wrap_srt_text,
)


def test_subtitle_timing_guard_clamps_to_video_duration_and_wraps_text(tmp_path):
    source = tmp_path / "source.srt"
    output = tmp_path / "fixed.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:12,000\nĐây là một câu subtitle rất dài cần được xuống dòng hợp lý\n\n"
        "2\n00:00:11,500 --> 00:00:13,000\nKhông được vượt duration\n",
        encoding="utf-8",
    )

    SubtitleTimingGuard().guard_timing(str(source), target_duration=10, output_path=str(output))

    blocks = parse_srt_blocks(str(output))
    assert blocks
    assert blocks[-1].end == 10
    assert all(len(block.text.splitlines()) <= 2 for block in blocks)


def test_subtitle_timing_guard_does_not_drop_long_text(tmp_path):
    source = tmp_path / "source.srt"
    output = tmp_path / "fixed.srt"
    text = "Một câu rất dài có nhiều thông tin quan trọng không được phép bị cắt mất khi render subtitle"
    source.write_text(f"1\n00:00:00,000 --> 00:00:04,000\n{text}\n", encoding="utf-8")

    SubtitleTimingGuard().guard_timing(str(source), target_duration=5, output_path=str(output), max_chars_per_line=18)

    blocks = parse_srt_blocks(str(output))
    combined = " ".join(block.text.replace("\n", " ") for block in blocks)

    assert len(blocks) == 1
    assert all(len(block.text.splitlines()) <= 2 for block in blocks)
    assert combined == f"{text}."


def test_subtitle_timing_guard_can_shift_asr_subtitles_earlier(tmp_path):
    source = tmp_path / "source.srt"
    output = tmp_path / "fixed.srt"
    source.write_text("1\n00:00:01,000 --> 00:00:02,000\nXin chào\n", encoding="utf-8")

    SubtitleTimingGuard().guard_timing(
        str(source),
        target_duration=5,
        output_path=str(output),
        time_offset_seconds=-0.25,
    )

    blocks = parse_srt_blocks(str(output))
    assert blocks[0].start == 0.75
    assert blocks[0].end == 1.75


def test_wrap_srt_text_preserves_all_wrapped_lines():
    lines = wrap_srt_text("Một câu tiếng Việt khá dài để kiểm tra xuống dòng", max_chars_per_line=18, max_lines=2)

    assert len(lines) > 2
    assert " ".join(lines) == "Một câu tiếng Việt khá dài để kiểm tra xuống dòng"


def test_split_text_for_display_keeps_complete_sentence_when_it_fits_two_lines():
    text = "Mot cau tieng Viet kha dai de kiem tra xuong dong thanh mot block"
    chunks = split_text_for_display(text, max_chars_per_line=18, max_lines=2)

    assert len(chunks) == 1
    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)
    assert " ".join(chunks[0].splitlines()) == f"{text}."


def test_split_text_for_display_splits_multiple_sentences():
    chunks = split_text_for_display(
        "Cau mot hien rieng. Cau hai hien rieng.",
        max_chars_per_line=18,
        max_lines=2,
    )

    assert [" ".join(chunk.splitlines()) for chunk in chunks] == ["Cau mot hien rieng.", "Cau hai hien rieng."]


def test_split_text_for_display_splits_extremely_long_sentence_without_dropping_words():
    text = (
        "Mot cau qua dai de hien thi trong hai dong nen can duoc tach mem nhung van giu du thong tin "
        "quan trong ve san pham cach su dung loi ich va ly do nen mua ngay hom nay"
    )

    chunks = split_text_for_display(text, max_chars_per_line=18, max_lines=2)

    assert len(chunks) > 1
    assert all(len(chunk.splitlines()) <= 2 for chunk in chunks)
    assert " ".join(chunk.replace("\n", " ") for chunk in chunks) == f"{text}."


def test_format_srt_timestamp():
    assert format_srt_timestamp(1.234) == "00:00:01,234"
