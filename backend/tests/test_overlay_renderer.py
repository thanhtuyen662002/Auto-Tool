from __future__ import annotations

from app.modules.renderer import overlay_renderer
from app.modules.renderer.overlay_renderer import OverlayRenderer
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
