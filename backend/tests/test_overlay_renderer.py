from __future__ import annotations

from types import SimpleNamespace

from app.modules.renderer import overlay_renderer
from app.adapters.ffmpeg_adapter import FFmpegError
from app.modules.renderer.overlay_renderer import OverlayRenderer
from app.modules.script_writer.script_writer import ProductVideoScript
from app.schemas.project_schema import ProjectConfig


def test_music_mix_filter_keeps_music_steady_by_default(monkeypatch):
    commands: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]) -> None:
        commands.append(args)

    monkeypatch.setattr(overlay_renderer, "run_ffmpeg", fake_run_ffmpeg)

    OverlayRenderer()._run_ffmpeg_with_music(
        visual_video_path="visual.mp4",
        voice_path="voice.wav",
        music_path="music.mp3",
        output_path="final.mp4",
        video_filters="drawbox=x=0:y=0:w=iw:h=100:color=black@0.55:t=fill",
        voice_duration=8.0,
        duration=12.0,
        config=_config(),
    )

    filter_complex = commands[0][commands[0].index("-filter_complex") + 1]
    assert "sidechaincompress" not in filter_complex
    assert "asplit=2[voice_for_duck][voice_for_mix]" not in filter_complex
    assert "[voice][music]amix" in filter_complex
    assert "[music][voice]sidechaincompress" not in filter_complex


def test_music_ducking_filter_splits_voice_when_enabled(monkeypatch):
    commands: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]) -> None:
        commands.append(args)

    monkeypatch.setattr(overlay_renderer, "run_ffmpeg", fake_run_ffmpeg)

    OverlayRenderer()._run_ffmpeg_with_music(
        visual_video_path="visual.mp4",
        voice_path="voice.wav",
        music_path="music.mp3",
        output_path="final.mp4",
        video_filters="drawbox=x=0:y=0:w=iw:h=100:color=black@0.55:t=fill",
        voice_duration=8.0,
        duration=12.0,
        config=_config(duck_under_voice=True),
    )

    filter_complex = commands[0][commands[0].index("-filter_complex") + 1]
    assert "asplit=2[voice_for_duck][voice_for_mix]" in filter_complex
    assert "[music][voice_for_duck]sidechaincompress" in filter_complex
    assert "[voice_for_mix][music_ducked]amix" in filter_complex
    assert "[voice][music]amix" not in filter_complex


def test_overlay_renderer_falls_back_when_ass_style_render_fails(tmp_path, monkeypatch):
    renderer = OverlayRenderer()
    fallback_calls: list[bool] = []

    monkeypatch.setattr(
        overlay_renderer,
        "probe_video",
        lambda path: SimpleNamespace(duration=8.0, width=1080, height=1920),
    )
    monkeypatch.setattr(overlay_renderer, "probe_media_duration", lambda path: 8.0)
    monkeypatch.setattr(
        overlay_renderer,
        "build_overlay_asset",
        lambda preset, width, height, output_path: output_path,
    )

    def fail_style_render(**kwargs):
        raise FFmpegError("ASS render failed")

    def fallback_render(**kwargs):
        fallback_calls.append(kwargs["include_subtitles"])

    monkeypatch.setattr(renderer, "_render_with_overlay_asset", fail_style_render)
    monkeypatch.setattr(renderer, "_render_with_filters", fallback_render)

    result = renderer.render_final_video(
        visual_video_path=str(tmp_path / "visual.mp4"),
        voice_path=str(tmp_path / "voice.wav"),
        subtitle_path=str(tmp_path / "video_001_sub.ass"),
        script=_script(),
        config=_config(),
        output_path=str(tmp_path / "video_001.mp4"),
        fallback_subtitle_path=str(tmp_path / "video_001_sub.srt"),
    )

    assert result.endswith("video_001.mp4")
    assert fallback_calls == [True]
    assert renderer.last_visual_style["fallback_used"] is True
    assert renderer.last_visual_style["subtitle_format"] == "srt"


def _config(duck_under_voice: bool = False) -> ProjectConfig:
    return ProjectConfig.model_validate(
        {
            "project_name": "test",
            "source_folder": ".",
            "output_folder": ".",
            "product": {
                "name": "Product",
                "brand": "Brand",
                "description": "Description",
                "features": ["Feature"],
                "cta": "CTA",
            },
            "render": {
                "output_count": 1,
                "duration": 12,
                "aspect_ratio": "9:16",
                "resolution": "1080x1920",
                "fps": 30,
            },
            "effects": {
                "cut_intensity": 65,
                "speed_variation": 30,
                "grain": 12,
                "zoom_motion": 20,
                "overlay_height": 22,
                "subtitle_size": 54,
            },
            "ai": {
                "text_model": "gemini-test",
                "tone": "friendly_reviewer",
                "language": "vi",
                "gemini_api_keys": [],
            },
            "music": {
                "enabled": True,
                "source_folder": None,
                "source_file": None,
                "volume": 0.12,
                "fade_in": 0.5,
                "fade_out": 0.8,
                "duck_under_voice": duck_under_voice,
            },
        }
    )


def _script() -> ProductVideoScript:
    return ProductVideoScript.model_validate(
        {
            "hook": "Hook",
            "voiceover": [{"time_hint": "0-8s", "text": "Một câu voice test."}],
            "subtitles": [{"start_hint": 0, "end_hint": 8, "text": "Một câu voice test."}],
            "cta": "CTA",
            "caption": "Caption",
            "hashtags": ["#test"],
        }
    )
