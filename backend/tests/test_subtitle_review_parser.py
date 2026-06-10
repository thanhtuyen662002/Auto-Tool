from __future__ import annotations

from pathlib import Path

from app.modules.subtitle_review.subtitle_parser import parse_srt_to_lines, write_lines_to_srt


def test_parse_srt_maps_source_and_translation_by_index(tmp_path: Path):
    source = tmp_path / "source.srt"
    translated = tmp_path / "translated.srt"
    source.write_text(
        "1\n00:00:00,000 --> 00:00:01,200\nNi hao\n\n"
        "2\n00:00:01,200 --> 00:00:02,400\nXie xie\n",
        encoding="utf-8",
    )
    translated.write_text(
        "1\n00:00:00,000 --> 00:00:01,200\nXin chao\n\n"
        "2\n00:00:01,200 --> 00:00:02,400\nCam on\n",
        encoding="utf-8",
    )

    lines = parse_srt_to_lines(str(translated), source_srt_path=str(source))

    assert [line.index for line in lines] == [1, 2]
    assert lines[0].start_ms == 0
    assert lines[0].end_ms == 1200
    assert lines[0].source_text == "Ni hao"
    assert lines[0].translated_text == "Xin chao"
    assert lines[1].source_text == "Xie xie"


def test_write_lines_to_srt_prefers_manual_edit(tmp_path: Path):
    translated = tmp_path / "translated.srt"
    translated.write_text("1\n00:00:00,000 --> 00:00:01,000\nAuto line\n", encoding="utf-8")
    lines = parse_srt_to_lines(str(translated))
    lines[0] = lines[0].model_copy(update={"edited_text": "Manual line"})

    output = tmp_path / "corrected.srt"
    write_lines_to_srt(lines, str(output))

    text = output.read_text(encoding="utf-8")
    assert "Manual line" in text
    assert "Auto line" not in text
