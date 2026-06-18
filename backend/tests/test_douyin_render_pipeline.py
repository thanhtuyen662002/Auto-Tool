from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.douyin_render_pipeline import (
    DouyinRenderPipeline,
    _build_smooth_voiceover_lines,
    _plan_voiceover_video_slowdown,
    _scale_subtitle_blocks,
)
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.douyin_reup.subtitle_timing_guard import SubtitleBlock
from app.modules.script_writer.script_writer import SubtitleLine
from app.modules.tts.tts_schema import TTSResult
from app.schemas.media_schema import MediaFile


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


def test_smooth_voiceover_adds_sentence_breaks_between_short_utterances():
    blocks = [
        SubtitleBlock(index=1, start=0.0, end=0.4, text="Troi oi"),
        SubtitleBlock(index=2, start=0.42, end=0.9, text="Sao lai the"),
        SubtitleBlock(index=3, start=0.92, end=1.6, text="nhung van on"),
    ]

    lines = _build_smooth_voiceover_lines(blocks)

    assert len(lines) == 1
    assert lines[0].text == "Troi oi. Sao lai the nhung van on."


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


class FakeTimelineVoiceGenerator:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.last_subtitle_timeline = [
            SubtitleLine(start_hint=0.0, end_hint=0.8, text="Subtitle theo voice"),
        ]
        self.last_tts_result: TTSResult | None = None
        self.kwargs: dict | None = None

    def generate_voiceover(self, script, output_dir, **kwargs):
        self.kwargs = kwargs
        output_path = Path(output_dir) / kwargs["filename"]
        output_path.write_bytes(b"voice")
        self.last_tts_result = TTSResult(
            provider="edge_tts",
            output_path=str(output_path),
            duration=0.8,
            format="mp3",
            success=True,
        )
        return str(output_path)


def test_douyin_voiceover_uses_flowing_tts_timeline(tmp_path):
    source_srt = tmp_path / "source.srt"
    source_srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,500\nCau mot\n\n"
        "2\n00:00:00,500 --> 00:00:01,000\nCau hai\n",
        encoding="utf-8",
    )
    voice = FakeTimelineVoiceGenerator()
    pipeline = DouyinRenderPipeline(voice_generator=voice)

    path = pipeline._generate_voiceover_from_srt(
        subtitle_srt_path=str(source_srt),
        output_dir=str(tmp_path),
        output_name="out.mp4",
        settings=DouyinReupSettings(enabled=True, generate_voiceover_for_silent_video=True),
        target_duration=2.0,
    )

    assert Path(path).exists()
    assert voice.kwargs is not None
    assert voice.kwargs["lock_subtitle_timing"] is False


def test_render_uses_voiceover_timeline_for_burned_subtitle(tmp_path, monkeypatch):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")
    source_srt = tmp_path / "source.srt"
    source_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nCau goc\n", encoding="utf-8")
    voice = FakeTimelineVoiceGenerator()
    pipeline = DouyinRenderPipeline(voice_generator=voice)

    monkeypatch.setattr(
        "app.modules.douyin_reup.douyin_render_pipeline.probe_video",
        lambda path: MediaFile(
            path=path,
            duration=2,
            width=1080,
            height=1920,
            fps=30,
            has_audio=False,
            format_name="mov,mp4",
        ),
    )

    def fake_run_render(self, **kwargs):
        Path(kwargs["output_path"]).write_bytes(b"mp4")

    monkeypatch.setattr(DouyinRenderPipeline, "_run_render", fake_run_render)

    result = pipeline.render_video_with_srt(
        video=type(
            "Video",
            (),
            {
                "path": str(video_path),
                "filename": video_path.name,
                "duration": 2,
                "width": 1080,
                "height": 1920,
                "fps": 30,
                "has_audio": False,
            },
        )(),
        subtitle_srt_path=str(source_srt),
        settings=DouyinReupSettings(
            enabled=True,
            generate_voiceover_for_silent_video=True,
            keep_original_audio=False,
            add_bgm=False,
            add_overlay=False,
        ),
        output_dir=str(tmp_path / "out"),
        output_name="rendered.mp4",
    )

    render_srt = Path(result["render_subtitle_srt_file"])
    assert render_srt.name == "rendered_vi_voiceover.srt"
    assert "Subtitle theo voice" in render_srt.read_text(encoding="utf-8")
