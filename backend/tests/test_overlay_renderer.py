from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

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
    assert len(commands) == 2
    assert "[1:a]volume=0.1200" in filter_complex
    assert "afade=t=out:st=11.200:d=0.800,atrim=0:12.000,asetpts=PTS-STARTPTS[music]" in filter_complex
    assert "afade=t=out:st=11.200:d=0.800,apad,atrim=0:12.000" not in filter_complex
    assert commands[1][commands[1].index("-filter_complex") + 1] == (
        "[0:v]drawbox=x=0:y=0:w=iw:h=100:color=black@0.55:t=fill[vout]"
    )
    assert commands[1][commands[1].index("-map") + 3] == "1:a:0"


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


def test_overlay_asset_music_filter_does_not_pad_looped_music(monkeypatch):
    commands: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]) -> None:
        commands.append(args)

    monkeypatch.setattr(overlay_renderer, "run_ffmpeg", fake_run_ffmpeg)

    OverlayRenderer()._run_ffmpeg_with_overlay_and_music(
        visual_video_path="visual.mp4",
        overlay_asset_path="overlay.png",
        voice_path="voice.wav",
        music_path="music.mp3",
        output_path="final.mp4",
        video_chain="[0:v][1:v]overlay=0:0[vout]",
        voice_duration=8.0,
        duration=12.0,
        config=_config(),
    )

    audio_filter = commands[0][commands[0].index("-filter_complex") + 1]
    video_filter = commands[1][commands[1].index("-filter_complex") + 1]
    assert len(commands) == 2
    assert "[1:a]volume=0.1200" in audio_filter
    assert video_filter == "[0:v][1:v]overlay=0:0[vout]"
    assert "-loop" in commands[1]
    assert commands[1][commands[1].index("-map") + 3] == "2:a:0"
    assert "afade=t=out:st=11.200:d=0.800,atrim=0:12.000,asetpts=PTS-STARTPTS[music]" in audio_filter
    assert "afade=t=out:st=11.200:d=0.800,apad,atrim=0:12.000" not in audio_filter


def test_overlay_asset_render_loops_image_for_full_video(monkeypatch):
    commands: list[list[str]] = []

    def fake_run_ffmpeg(args: list[str]) -> None:
        commands.append(args)

    monkeypatch.setattr(overlay_renderer, "run_ffmpeg", fake_run_ffmpeg)

    OverlayRenderer()._render_with_overlay_asset(
        visual_video_path="visual.mp4",
        overlay_asset_path="overlay.png",
        voice_path="voice.wav",
        subtitle_path="sub.ass",
        config=_config(),
        output_path="final.mp4",
        duration=12.0,
        voice_duration=8.0,
        width=1080,
        height=1920,
        include_subtitles=True,
        music_path=None,
    )

    command = commands[0]
    filter_complex = command[command.index("-filter_complex") + 1]
    assert command[command.index("-loop") + 1] == "1"
    assert command[command.index("-loop") + 2] == "-i"
    assert command[command.index("-loop") + 3] == "overlay.png"
    assert "scale=1080:1920[overlay]" in filter_complex
    assert "overlay=0:0:eof_action=repeat:repeatlast=1[vbase]" in filter_complex


def test_custom_overlay_cover_builds_full_width_bottom_region(tmp_path):
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "overlay.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(source_path)

    result = OverlayRenderer._build_custom_overlay_asset(
        source_path=str(source_path),
        output_path=str(output_path),
        width=1080,
        height=1920,
        config=_config(overlay_mode="custom", custom_overlay_height_percent=33),
    )

    image = Image.open(result).convert("RGBA")
    assert image.size == (1080, 1920)
    assert image.getchannel("A").getbbox() == (0, 1286, 1080, 1920)


def test_custom_overlay_contain_keeps_whole_image_centered(tmp_path):
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "overlay.png"
    Image.new("RGBA", (100, 100), (255, 0, 0, 255)).save(source_path)

    result = OverlayRenderer._build_custom_overlay_asset(
        source_path=str(source_path),
        output_path=str(output_path),
        width=1080,
        height=1920,
        config=_config(
            overlay_mode="custom",
            custom_overlay_height_percent=33,
            custom_overlay_fit_mode="contain",
        ),
    )

    image = Image.open(result).convert("RGBA")
    assert image.size == (1080, 1920)
    assert image.getchannel("A").getbbox() == (223, 1286, 857, 1920)


def test_render_final_video_can_disable_overlay(tmp_path, monkeypatch):
    renderer = OverlayRenderer()
    calls: list[dict] = []

    monkeypatch.setattr(
        overlay_renderer,
        "probe_video",
        lambda path: SimpleNamespace(duration=8.0, width=1080, height=1920),
    )
    monkeypatch.setattr(overlay_renderer, "probe_media_duration", lambda path: 8.0)

    def fake_render_with_filters(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(renderer, "_render_with_filters", fake_render_with_filters)

    result = renderer.render_final_video(
        visual_video_path=str(tmp_path / "visual.mp4"),
        voice_path=str(tmp_path / "voice.wav"),
        subtitle_path=str(tmp_path / "video_001_sub.ass"),
        script=_script(),
        config=_config(overlay_mode="none"),
        output_path=str(tmp_path / "video_001.mp4"),
        fallback_subtitle_path=str(tmp_path / "video_001_sub.srt"),
    )

    assert result.endswith("video_001.mp4")
    assert calls[0]["draw_overlay"] is False
    assert renderer.last_visual_style["overlay_mode"] == "none"
    assert renderer.last_visual_style["overlay_asset"] is None


def test_custom_overlay_folder_uses_first_supported_image(tmp_path):
    (tmp_path / "readme.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "b.jpg").write_bytes(b"fake")
    (tmp_path / "a.png").write_bytes(b"fake")

    selected = OverlayRenderer._select_custom_overlay_asset(str(tmp_path))

    assert selected.endswith("a.png")


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


def _config(
    duck_under_voice: bool = False,
    overlay_mode: str = "preset",
    custom_overlay_height_percent: int | None = None,
    custom_overlay_fit_mode: str = "cover",
) -> ProjectConfig:
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
            "visual_style": {
                "preset_id": "clean_review_light",
                "custom_overrides": None,
                "overlay_mode": overlay_mode,
                "custom_overlay_path": None,
                "custom_overlay_height_percent": custom_overlay_height_percent,
                "custom_overlay_fit_mode": custom_overlay_fit_mode,
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
