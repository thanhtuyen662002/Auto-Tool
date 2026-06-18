from __future__ import annotations

import json

from app.modules.douyin_reup.douyin_render_pipeline import (
    DouyinRenderPipeline,
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
    assert any("subtitle_cover_auto_position" in warning for warning in warnings)
