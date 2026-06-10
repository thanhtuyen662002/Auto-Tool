from __future__ import annotations

from app.modules.douyin_reup_presets import DouyinReupPresetService


def test_silent_presets_have_expected_settings():
    service = DouyinReupPresetService()
    chill = service.apply_preset("silent_chill_immersive")
    voice = service.apply_preset("silent_product_voiceover")
    sales = service.apply_preset("silent_sales_recut")

    assert chill.silent_mode_strategy == "chill_immersive"
    assert chill.generate_voiceover_for_silent_video is False
    assert voice.generate_voiceover_for_silent_video is True
    assert voice.silent_voiceover_voice == "vi-VN-HoaiMyNeural"
    assert sales.silent_mode_strategy == "sales_recut"
