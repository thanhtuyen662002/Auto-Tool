from __future__ import annotations

from app.modules.douyin_reup.douyin_render_pipeline import (
    DouyinRenderPipeline,
    _build_smooth_voiceover_lines,
    _plan_voiceover_video_slowdown,
    _scale_subtitle_blocks,
)
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
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
