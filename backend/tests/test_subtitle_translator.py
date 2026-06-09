from __future__ import annotations

from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.douyin_reup.subtitle_translator import SubtitleTranslator, build_srt_translation_prompt


def test_build_srt_translation_prompt_requires_json_response():
    prompt = build_srt_translation_prompt("1\n00:00:00,000 --> 00:00:01,000\n你好\n")

    assert '"srt"' in prompt
    assert "Không đổi timestamp" in prompt
    assert "không rút gọn ý" in prompt


def test_subtitle_translator_falls_back_to_source_when_gemini_fails(tmp_path, monkeypatch):
    source = tmp_path / "source.srt"
    output = tmp_path / "vi.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")

    def fail_translate(*args, **kwargs):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(SubtitleTranslator, "_translate_blocks_with_gemini", fail_translate)
    result = SubtitleTranslator().translate_srt(str(source), str(output), api_keys=["fake"])

    assert result.provider == "fallback_source_text"
    assert output.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert "Gemini thất bại" in result.warnings[0]


def test_subtitle_translator_writes_gemini_result(tmp_path, monkeypatch):
    source = tmp_path / "source.srt"
    output = tmp_path / "vi.srt"
    source.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")

    def fake_translate(self, blocks, **kwargs):
        return [block.__class__(index=block.index, start=block.start, end=block.end, text="Xin chào") for block in blocks]

    monkeypatch.setattr(SubtitleTranslator, "_translate_blocks_with_gemini", fake_translate)
    result = SubtitleTranslator().translate_srt(str(source), str(output), api_keys=["fake"])

    assert result.provider == "gemini"
    blocks = parse_srt_blocks(str(output))
    assert blocks[0].text == "Xin chào"
