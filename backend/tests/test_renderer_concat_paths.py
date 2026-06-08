from __future__ import annotations

from pathlib import Path

from app.modules.renderer import renderer as renderer_module
from app.modules.renderer.renderer import Renderer
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip
from app.schemas.project_schema import AISettings, EffectSettings, ProductInfo, ProjectConfig, RenderSettings


def test_renderer_concat_file_uses_paths_relative_to_concat_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured_concat: list[str] = []

    def fake_render_clip(_self, _clip, output_path: Path, _config) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake clip")

    def fake_run_ffmpeg(args: list[str]) -> None:
        concat_path = Path(args[args.index("-i") + 1])
        captured_concat.extend(concat_path.read_text(encoding="utf-8").splitlines())
        Path(args[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(args[-1]).write_bytes(b"fake visual")

    monkeypatch.setattr(Renderer, "_render_clip", fake_render_clip)
    monkeypatch.setattr(renderer_module, "run_ffmpeg", fake_run_ffmpeg)

    timeline = Timeline(
        output_index=1,
        target_duration=2,
        clips=[
            TimelineClip(source_path="source_a.mp4", start=0, end=1, duration=1, speed=1),
            TimelineClip(source_path="source_b.mp4", start=1, end=2, duration=1, speed=1),
        ],
    )

    output_path = Renderer().render_timeline(
        timeline,
        _config(),
        "examples/outputs/test-project",
        base_name="video_001",
    )

    assert captured_concat == ["file 'clip_001.mp4'", "file 'clip_002.mp4'"]
    assert Path(output_path).exists()


def _config() -> ProjectConfig:
    return ProjectConfig(
        project_name="test-project",
        source_folder="source",
        output_folder="examples/outputs",
        product=ProductInfo(
            name="Sản phẩm test",
            brand="Brand",
            description="Mô tả test",
            features=["Tính năng test"],
            cta="Xem ngay",
        ),
        render=RenderSettings(
            output_count=1,
            duration=2,
            aspect_ratio="9:16",
            resolution="1080x1920",
            fps=30,
        ),
        effects=EffectSettings(
            cut_intensity=70,
            speed_variation=0,
            grain=0,
            zoom_motion=0,
            overlay_height=33,
            subtitle_size=54,
        ),
        ai=AISettings(
            text_model="test",
            tone="friendly_reviewer",
            language="vi",
        ),
    )
