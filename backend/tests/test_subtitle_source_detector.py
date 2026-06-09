from __future__ import annotations

from app.modules.douyin_reup.douyin_schema import DouyinReupSettings, DouyinVideoItem
from app.modules.douyin_reup.subtitle_source_detector import SubtitleSourceDetector


def _video(tmp_path, sidecar: str | None = None, embedded: bool = False) -> DouyinVideoItem:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    return DouyinVideoItem(
        path=str(video),
        filename=video.name,
        duration=10,
        width=1080,
        height=1920,
        fps=30,
        has_audio=True,
        sidecar_srt_path=sidecar,
        embedded_subtitle_found=embedded,
    )


def test_detector_prefers_sidecar_srt(tmp_path):
    sidecar = tmp_path / "clip.srt"
    sidecar.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n", encoding="utf-8")
    detector = SubtitleSourceDetector()

    result = detector.detect_source(_video(tmp_path, str(sidecar)), DouyinReupSettings(enabled=True), str(tmp_path / "work"))

    assert result.source_type == "sidecar_srt"
    assert result.source_srt_path is not None
    assert result.source_srt_path.endswith("_source_zh.srt")


def test_detector_uses_asr_when_no_srt(tmp_path):
    class FakeASR:
        def transcribe_to_srt(self, video_path, output_srt_path, **kwargs):
            with open(output_srt_path, "w", encoding="utf-8") as target:
                target.write("1\n00:00:00,000 --> 00:00:01,000\n你好\n")
            return output_srt_path

    settings = DouyinReupSettings(
        enabled=True,
        use_sidecar_srt=False,
        use_embedded_subtitle=False,
        use_asr_if_no_subtitle=True,
    )
    detector = SubtitleSourceDetector(asr_service=FakeASR())

    result = detector.detect_source(_video(tmp_path), settings, str(tmp_path / "work"))

    assert result.source_type == "asr"
    assert result.source_srt_path is not None
