from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.hardsub_ocr_service import HardSubOCRService
from app.modules.hardsub_ocr.ocr_provider import MockOCRProvider


class FakeSampler:
    def sample_frames(self, video_path, output_dir, sample_fps=2.0):
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        frames = []
        for timestamp in (0, 500, 1000):
            path = target / f"frame_{timestamp:08d}ms.jpg"
            path.write_bytes(b"fake")
            frames.append((timestamp, str(path)))
        return frames


def test_hardsub_ocr_service_creates_srt_and_debug_json(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        "app.modules.hardsub_ocr.hardsub_ocr_service.probe_video",
        lambda _path: SimpleNamespace(duration=3.0, width=1080, height=1920),
    )
    provider = MockOCRProvider({0: ("这个真的很好用", 0.9), 500: ("这个真的很好用", 0.88), 1000: ("价格也很便宜", 0.86)})

    result = HardSubOCRService(frame_sampler=FakeSampler(), provider=provider).extract_hardsub_to_srt(
        str(video),
        str(tmp_path / "out"),
        DouyinReupSettings(enabled=True, ocr_provider="mock_ocr"),
    )

    assert result.source_srt_path
    assert Path(result.source_srt_path).exists()
    assert result.debug_json_path
    assert Path(result.debug_json_path).exists()
    assert result.detected_line_count == 2
