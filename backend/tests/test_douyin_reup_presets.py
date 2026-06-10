from __future__ import annotations

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.douyin_reup_presets import DouyinReupPresetService


def test_douyin_reup_presets_include_required_modes():
    presets = DouyinReupPresetService().list_presets()
    ids = {preset.id.value for preset in presets}

    assert ids == {
        "safe_review",
        "fast_auto",
        "ocr_priority",
        "voice_priority",
        "clean_subtitle_only",
        "music_recut",
    }
    assert [preset.id.value for preset in presets if preset.is_default] == ["safe_review"]


def test_apply_preset_preserves_user_bgm_folder_and_accepts_alias_overrides():
    service = DouyinReupPresetService()
    current = DouyinReupSettings(enabled=True, music_folder="D:/music")

    settings = service.apply_preset(
        "ocr_priority",
        current_settings=current,
        overrides={
            "use_existing_srt_if_available": False,
            "extract_embedded_subtitle_if_available": False,
            "bgm_folder": "D:/picked-music",
            "process_mode": "all_videos",
            "max_videos": 3,
        },
    )

    assert settings.preset_id == "ocr_priority"
    assert settings.preset_name == "OCR Priority"
    assert settings.music_folder == "D:/picked-music"
    assert settings.use_sidecar_srt is False
    assert settings.use_embedded_subtitle is False
    assert settings.process_mode == "all"
    assert settings.max_videos == 3


def test_apply_clean_subtitle_only_disables_bgm_and_overlay():
    settings = DouyinReupPresetService().apply_preset("clean_subtitle_only")

    assert settings.add_bgm is False
    assert settings.add_overlay is False
    assert settings.burn_subtitle is True
