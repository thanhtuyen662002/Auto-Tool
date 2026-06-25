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
    sidecar.write_text("1\n00:00:00,000 --> 00:00:01,000\n\u4f60\u597d\n", encoding="utf-8")
    detector = SubtitleSourceDetector()

    result = detector.detect_source(_video(tmp_path, str(sidecar)), DouyinReupSettings(enabled=True), str(tmp_path / "work"))

    assert result.source_type == "sidecar_srt"
    assert result.source_srt_path is not None
    assert result.source_srt_path.endswith("_source_zh.srt")


def test_detector_uses_asr_when_no_srt(tmp_path):
    class FakeASR:
        def transcribe_to_srt(self, video_path, output_srt_path, **kwargs):
            with open(output_srt_path, "w", encoding="utf-8") as target:
                target.write(
                    "1\n00:00:00,000 --> 00:00:01,200\n\u8fd9\u4e2a\u6536\u7eb3\u76d2\u5bb9\u91cf\u5f88\u5927\n\n"
                    "2\n00:00:01,500 --> 00:00:02,800\n\u76d6\u5b50\u6263\u8d77\u6765\u4e5f\u5f88\u7a33\n\n"
                    "3\n00:00:03,000 --> 00:00:04,200\n\u653e\u684c\u9762\u4e0a\u6bd4\u8f83\u6574\u9f50\n"
                )
            return output_srt_path

    settings = DouyinReupSettings(
        enabled=True,
        use_sidecar_srt=False,
        use_embedded_subtitle=False,
        use_ocr_if_no_subtitle=False,
        use_asr_if_no_subtitle=True,
        asr_subprocess_isolation=False,
    )
    detector = SubtitleSourceDetector(asr_service=FakeASR())

    result = detector.detect_source(_video(tmp_path), settings, str(tmp_path / "work"))

    assert result.source_type == "asr"
    assert result.source_srt_path is not None
    assert result.subtitle_quality_score > 0


def test_detector_rejects_low_quality_asr(tmp_path):
    class NoisyASR:
        def transcribe_to_srt(self, video_path, output_srt_path, **kwargs):
            with open(output_srt_path, "w", encoding="utf-8") as target:
                target.write("1\n00:00:00,000 --> 00:00:00,800\n\u0110i, \u0111i, \u0111i.\n")
            return output_srt_path

    settings = DouyinReupSettings(
        enabled=True,
        use_sidecar_srt=False,
        use_embedded_subtitle=False,
        use_ocr_if_no_subtitle=False,
        use_ocr_if_asr_failed=False,
        use_asr_if_no_subtitle=True,
        asr_subprocess_isolation=False,
    )

    result = SubtitleSourceDetector(asr_service=NoisyASR()).detect_source(_video(tmp_path), settings, str(tmp_path / "work"))

    assert result.source_type == "none"
    assert result.source_srt_path is None
    assert result.fallback_mode == "music_only_safe"
    assert result.subtitle_rejected_sources
