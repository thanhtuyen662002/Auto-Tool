from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRRegion
from app.modules.hardsub_ocr.hardsub_ocr_service import HardSubOCRService
from app.modules.hardsub_ocr.ocr_provider import BaseOCRProvider, MockOCRProvider


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

    progress_events = []
    result = HardSubOCRService(frame_sampler=FakeSampler(), provider=provider).extract_hardsub_to_srt(
        str(video),
        str(tmp_path / "out"),
        DouyinReupSettings(enabled=True, ocr_provider="mock_ocr"),
        progress_callback=progress_events.append,
    )

    assert result.source_srt_path
    assert Path(result.source_srt_path).exists()
    assert result.debug_json_path
    assert Path(result.debug_json_path).exists()
    assert result.detected_line_count == 2
    assert progress_events[0]["current_step"] == "ocr_probe"
    assert any(event["current_step"] == "ocr_recognizing" for event in progress_events)
    assert progress_events[-1]["progress"] == 100


class RegionAwareOCRProvider(BaseOCRProvider):
    provider_name = "region_aware"

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        match = re.search(r"(\d+)ms", Path(image_path).stem)
        timestamp_ms = int(match.group(1)) if match else 0
        if region.y > 0:
            return OCRFrameResult(timestamp_ms=timestamp_ms, frame_path=image_path, region=region, text="", confidence=0.0)
        return OCRFrameResult(
            timestamp_ms=timestamp_ms,
            frame_path=image_path,
            region=region,
            text="\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
            confidence=0.86,
        )


def test_hardsub_ocr_retries_full_frame_when_bottom_region_is_weak(tmp_path: Path, monkeypatch):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    monkeypatch.setattr(
        "app.modules.hardsub_ocr.hardsub_ocr_service.probe_video",
        lambda _path: SimpleNamespace(duration=3.0, width=1080, height=1920),
    )

    result = HardSubOCRService(frame_sampler=FakeSampler(), provider=RegionAwareOCRProvider()).extract_hardsub_to_srt(
        str(video),
        str(tmp_path / "out"),
        DouyinReupSettings(enabled=True, ocr_region_mode="bottom_auto"),
    )

    assert result.region_mode == "full_frame"
    assert result.detected_line_count == 1
    assert any("ocr_region_fallback_full_frame" in warning for warning in result.warnings)

    debug = json.loads(Path(result.debug_json_path).read_text(encoding="utf-8"))
    assert debug["requested_region_mode"] == "bottom_auto"
    assert debug["region_mode"] == "full_frame"
    assert debug["fallback_attempts"][0]["used"] is True
