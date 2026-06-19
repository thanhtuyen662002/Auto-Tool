from __future__ import annotations

import json

from app.modules.douyin_reup.douyin_render_pipeline import (
    DouyinRenderPipeline,
    _visual_style_overrides,
    _build_smooth_voiceover_lines,
    _plan_voiceover_video_slowdown,
    _scale_subtitle_blocks,
)
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock


def test_smooth_voiceover_groups_fragmented_subtitle_blocks():
    blocks = [
        SubtitleBlock(index=1, start=0.0, end=0.8, text="Nếu bạn đang tìm"),
        SubtitleBlock(index=2, start=0.82, end=1.6, text="một món dùng hằng ngày"),
        SubtitleBlock(index=3, start=1.62, end=2.4, text="thì mẫu này đáng xem."),
        SubtitleBlock(index=4, start=4.0, end=5.0, text="Xem kỹ trước khi chọn nhé."),
    ]

    lines = _build_smooth_voiceover_lines(blocks)

    assert len(lines) == 2
    assert lines[0].text == "Nếu bạn đang tìm một món dùng hằng ngày thì mẫu này đáng xem."
    assert lines[0].time_hint == "0.00-2.40s"
    assert lines[1].text == "Xem kỹ trước khi chọn nhé."


def test_smooth_voiceover_skips_near_duplicate_blocks():
    blocks = [
        SubtitleBlock(index=1, start=0.0, end=1.0, text="Sản phẩm này rất đáng xem"),
        SubtitleBlock(index=2, start=1.05, end=2.0, text="Sản phẩm này rất đáng xem"),
        SubtitleBlock(index=3, start=2.4, end=3.2, text="Thiết kế nhỏ gọn và dễ dùng."),
    ]

    lines = _build_smooth_voiceover_lines(blocks)

    joined = " ".join(line.text for line in lines)
    assert joined.count("Sản phẩm này rất đáng xem") == 1
    assert "Thiết kế nhỏ gọn" in joined


def test_voiceover_timing_plan_slows_dense_vietnamese_voiceover():
    settings = DouyinReupSettings(
        enabled=True,
        generate_voiceover_for_silent_video=True,
        voiceover_max_video_slowdown=1.15,
        voiceover_comfort_speedup=1.2,
    )
    blocks = [
        SubtitleBlock(
            index=1,
            start=0.0,
            end=1.0,
            text="Một câu tiếng Việt khá dài cần thêm thời gian để đọc tự nhiên hơn.",
        )
    ]

    plan = _plan_voiceover_video_slowdown(blocks, settings=settings, target_duration=5.0)
    scaled = _scale_subtitle_blocks(blocks, scale=plan["slowdown_factor"], target_duration=5.75)

    assert plan["slowdown_factor"] == 1.15
    assert plan["max_required_speed"] > settings.voiceover_comfort_speedup
    assert scaled[0].end == 1.15


def test_audio_filter_slows_original_audio_with_video_slowdown():
    audio_filter, label = DouyinRenderPipeline._build_audio_filter(
        has_original_audio=True,
        has_bgm=False,
        has_voiceover=False,
        original_audio_volume=0.8,
        bgm_volume=0.0,
        duration=11.5,
        bgm_input_index=None,
        voice_input_index=None,
        video_slowdown_factor=1.15,
    )

    assert label == "[aout]"
    assert "atempo=0.870" in audio_filter
    assert "atrim=0:11.500" in audio_filter


def test_audio_filter_can_reduce_original_voice_with_center_cancel():
    audio_filter, label = DouyinRenderPipeline._build_audio_filter(
        has_original_audio=True,
        has_bgm=False,
        has_voiceover=False,
        original_audio_volume=0.8,
        bgm_volume=0.0,
        duration=10.0,
        bgm_input_index=None,
        voice_input_index=None,
        reduce_original_voice=True,
        original_voice_reduction_strength=0.7,
    )

    assert label == "[aout]"
    assert "aformat=channel_layouts=stereo" in audio_filter
    assert "pan=stereo|c0=c0-0.700*c1|c1=c1-0.700*c0" in audio_filter


def test_visual_style_overrides_include_custom_vietnamese_subtitle_style():
    settings = DouyinReupSettings(
        enabled=True,
        subtitle_style_custom_enabled=True,
        subtitle_font_family="Arial",
        subtitle_font_size=64,
        subtitle_font_color="#ffe100",
        subtitle_stroke_color="#101010",
        subtitle_stroke_width=4,
        subtitle_shadow_enabled=True,
        subtitle_shadow_color="#222222",
        subtitle_shadow_opacity=0.6,
        subtitle_shadow_size=5,
        subtitle_max_chars_per_line=18,
        subtitle_max_lines=3,
    )

    overrides = _visual_style_overrides(settings)

    assert overrides["subtitle"]["font_size"] == 64
    assert overrides["subtitle"]["font_color"] == "#FFE100"
    assert overrides["subtitle"]["stroke_width"] == 4
    assert overrides["subtitle"]["shadow_size"] == 5
    assert overrides["subtitle"]["max_chars_per_line"] == 18
    assert overrides["subtitle"]["max_lines"] == 3


def test_subtitle_cover_options_use_ocr_debug_position(tmp_path):
    debug_path = tmp_path / "ocr_debug.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 1000, "width": 1080, "height": 700},
                "frames": [
                    {
                        "region": {"x": 0, "y": 1000, "width": 1080, "height": 700},
                        "raw_blocks": [
                            {
                                "box": [[100, 430], [980, 430], [980, 500], [100, 500]],
                                "text": "中文字幕",
                                "confidence": 0.8,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    warnings: list[str] = []
    settings = DouyinReupSettings(enabled=True, subtitle_cover_height_ratio=0.22)
    video = DouyinVideoItem(path="input.mp4", filename="input.mp4", duration=5, width=1080, height=1920, fps=30, has_audio=True)

    options = DouyinRenderPipeline()._subtitle_cover_options(
        settings=settings,
        video=video,
        source_ocr_debug_path=str(debug_path),
        warnings=warnings,
    )

    assert options["cover_background_height_ratio"] < 0.18
    assert options["cover_background_bottom_ratio"] > 0.15
    assert len(options["cover_background_segments"]) == 1
    assert any("subtitle_cover_auto_position" in warning for warning in warnings)


def test_subtitle_cover_options_fallback_to_thin_bottom_band_for_noisy_ocr(tmp_path):
    debug_path = tmp_path / "ocr_debug_noisy.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 720,
                "frame_height": 1280,
                "region": {"x": 0, "y": 704, "width": 720, "height": 448},
                "frames": [
                    {
                        "timestamp_ms": 9000,
                        "region": {"x": 0, "y": 704, "width": 720, "height": 448},
                        "raw_blocks": [
                            {
                                "box": [[210, 90], [270, 90], [270, 126], [210, 126]],
                                "text": "瓮",
                                "confidence": 0.003,
                            },
                            {
                                "box": [[480, 386], [540, 386], [540, 420], [480, 420]],
                                "text": "哑",
                                "confidence": 0.006,
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    warnings: list[str] = []
    settings = DouyinReupSettings(enabled=True, subtitle_cover_height_ratio=0.22)
    video = DouyinVideoItem(path="input.mp4", filename="input.mp4", duration=5, width=720, height=1280, fps=30, has_audio=True)

    options = DouyinRenderPipeline()._subtitle_cover_options(
        settings=settings,
        video=video,
        source_ocr_debug_path=str(debug_path),
        warnings=warnings,
    )

    assert options["cover_background_height_ratio"] == 0.12
    assert options["cover_background_bottom_ratio"] == 0
    assert options["cover_background_segments"] == []
    assert any("subtitle_cover_auto_position_bottom_fallback" in warning for warning in warnings)
