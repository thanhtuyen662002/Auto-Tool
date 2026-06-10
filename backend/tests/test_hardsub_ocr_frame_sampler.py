from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.modules.hardsub_ocr.frame_sampler import FrameSampler


def test_frame_sampler_uses_sample_fps_and_timestamp_filenames(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    monkeypatch.setattr(
        "app.modules.hardsub_ocr.frame_sampler.probe_video",
        lambda _path: SimpleNamespace(duration=2.0),
    )

    def fake_run_ffmpeg(args):
        Path(args[-1]).write_bytes(b"jpg")

    monkeypatch.setattr("app.modules.hardsub_ocr.frame_sampler.run_ffmpeg", fake_run_ffmpeg)

    frames = FrameSampler().sample_frames(str(video), str(tmp_path / "frames"), sample_fps=2.0, max_frames=10)

    assert [timestamp for timestamp, _path in frames] == [0, 500, 1000, 1500]
    assert Path(frames[1][1]).name == "frame_00000500ms.jpg"
