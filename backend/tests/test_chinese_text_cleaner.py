from __future__ import annotations

from app.modules.hardsub_ocr.chinese_text_cleaner import ChineseTextCleaner


def test_chinese_text_cleaner_removes_noise_and_keeps_chinese():
    cleaner = ChineseTextCleaner()

    assert cleaner.clean("  ✅ 这个 真 的 很 好 用!!!  ") == "这个 真 的 很 好 用!!!"


def test_looks_like_chinese_subtitle_requires_cjk():
    cleaner = ChineseTextCleaner()

    assert cleaner.looks_like_chinese_subtitle("这个真的很好用")
    assert not cleaner.looks_like_chinese_subtitle("12345 !!!")
    assert not cleaner.looks_like_chinese_subtitle("A")
