from __future__ import annotations

from pathlib import Path

from app.modules.douyin_reup.subtitle_quality_gate import evaluate_srt_quality, segment_is_low_quality


def _write_srt(path: Path, lines: list[tuple[float, float, str]]) -> Path:
    def ts(value: float) -> str:
        ms = int(round(value * 1000))
        hh, rest = divmod(ms, 3_600_000)
        mm, rest = divmod(rest, 60_000)
        ss, msec = divmod(rest, 1000)
        return f"{hh:02d}:{mm:02d}:{ss:02d},{msec:03d}"

    payload = []
    for index, (start, end, text) in enumerate(lines, start=1):
        payload.append(f"{index}\n{ts(start)} --> {ts(end)}\n{text}\n")
    path.write_text("\n".join(payload), encoding="utf-8")
    return path


def test_quality_gate_rejects_single_noise_phrases(tmp_path: Path):
    samples = [
        "Gi\u1ea3m c\u00e2n.",
        "\u0110i, \u0111i, \u0111i.",
        "\u300aPhim\u300b.",
    ]
    for index, text in enumerate(samples, start=1):
        path = _write_srt(tmp_path / f"noise_{index}.srt", [(0, 1, text)])

        result = evaluate_srt_quality(path, source_type="asr", video_duration=12)

        assert result.ok is False
        assert result.reasons


def test_quality_gate_rejects_short_hallucination_phrase_pack(tmp_path: Path):
    path = _write_srt(
        tmp_path / "phrase_pack.srt",
        [
            (0.0, 1.0, "Gi\u1ea3m c\u00e2n \u0111i"),
            (1.2, 2.0, "B\u00e9o qu\u00e1"),
            (2.2, 3.0, "Tr\u00e0 hoa c\u00fac"),
        ],
    )

    result = evaluate_srt_quality(path, source_type="asr", video_duration=14)

    assert result.ok is False
    assert "noise_phrase" in result.reasons


def test_quality_gate_rejects_short_low_coverage_subtitle(tmp_path: Path):
    path = _write_srt(tmp_path / "short.srt", [(0.0, 0.7, "\u00c0 n\u00e0y.")])

    result = evaluate_srt_quality(path, source_type="asr", video_duration=20)

    assert result.ok is False
    assert "too_few_blocks" in result.reasons
    assert "low_coverage" in result.reasons


def test_quality_gate_rejects_repeated_noise_blocks(tmp_path: Path):
    path = _write_srt(
        tmp_path / "repeat.srt",
        [
            (0, 1, "\u0111i \u0111i \u0111i"),
            (2, 3, "\u0111i \u0111i \u0111i"),
            (4, 5, "\u0111i \u0111i \u0111i"),
        ],
    )

    result = evaluate_srt_quality(path, source_type="asr", video_duration=12)

    assert result.ok is False
    assert "repetitive_text" in result.reasons or "noise_phrase" in result.reasons


def test_quality_gate_rejects_high_no_speech_asr_segment():
    rejected, reasons = segment_is_low_quality(
        "\u0110\u00e2y l\u00e0 c\u00e2u nghe kh\u00f4ng ch\u1eafc",
        no_speech_prob=0.8,
        avg_logprob=-0.2,
        compression_ratio=1.2,
    )

    assert rejected is True
    assert "high_no_speech_prob" in reasons


def test_quality_gate_passes_clear_dialogue(tmp_path: Path):
    path = _write_srt(
        tmp_path / "dialogue.srt",
        [
            (0, 2, "\u8fd9\u4e2a\u676f\u5b50\u62ff\u8d77\u6765\u5f88\u7a33\uff0c\u624b\u67c4\u4e5f\u6bd4\u8f83\u8212\u670d\u3002"),
            (2.5, 4.5, "\u5012\u6c34\u7684\u65f6\u5019\u4e0d\u4f1a\u660e\u663e\u6f0f\u51fa\u6765\u3002"),
            (5, 7, "\u653e\u5728\u684c\u9762\u4e0a\u770b\u8d77\u6765\u4e5f\u5f88\u5e72\u51c0\u3002"),
            (7.5, 9.5, "\u5982\u679c\u7ecf\u5e38\u559d\u8336\uff0c\u8fd9\u4e2a\u5bb9\u91cf\u6bd4\u8f83\u5408\u9002\u3002"),
        ],
    )

    result = evaluate_srt_quality(path, source_type="ocr_hardsub", video_duration=10, ocr_confidence=0.86)

    assert result.ok is True
    assert result.score > 0.8


def test_quality_gate_passes_clear_asr_subtitle(tmp_path: Path):
    path = _write_srt(
        tmp_path / "asr.srt",
        [
            (0, 2, "\u4eca\u5929\u6211\u4eec\u770b\u4e00\u4e0b\u8fd9\u4e2a\u6536\u7eb3\u76d2\u7684\u5bb9\u91cf\u3002"),
            (2.2, 4.2, "\u91cc\u9762\u53ef\u4ee5\u653e\u5f88\u591a\u5e38\u7528\u7684\u5c0f\u7269\u4ef6\u3002"),
            (4.5, 6.5, "\u76d6\u5b50\u6263\u4e0a\u4ee5\u540e\u4e5f\u6bd4\u8f83\u7a33\u3002"),
        ],
    )

    result = evaluate_srt_quality(path, source_type="asr", video_duration=8)

    assert result.ok is True
