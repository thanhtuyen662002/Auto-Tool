from __future__ import annotations

from app.modules.douyin_reup.douyin_render_pipeline import _build_smooth_voiceover_lines
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
