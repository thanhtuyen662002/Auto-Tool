from __future__ import annotations

from pathlib import Path

from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine
from app.modules.tts.tts_schema import TTSResult, TTSSettings
from app.modules.voice_generator import voice_generator
from app.modules.voice_generator.voice_generator import VoiceGenerator


class SwitchingTTSAdapter:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.last_provider: str | None = None
        self.locked_provider: str | None = None
        self.calls: list[tuple[str, str]] = []

    def lock_provider(self, provider: str | None) -> None:
        self.locked_provider = provider

    def generate_voice(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        if self.locked_provider == "edge_retry":
            provider = "edge_retry"
        elif not self.calls:
            provider = "edge"
        else:
            provider = "edge_retry"

        self.last_provider = provider
        self.calls.append((text, provider))
        Path(output_path).write_bytes(provider.encode("utf-8"))
        return TTSResult(
            provider=provider,
            output_path=output_path,
            duration=1.0,
            format=Path(output_path).suffix.lower().lstrip(".") or "wav",
            success=True,
        )


def test_timed_voiceover_regenerates_when_provider_changes(tmp_path, monkeypatch):
    adapter = SwitchingTTSAdapter()
    generator = VoiceGenerator(adapter)

    def fake_normalize(input_path: str, output_path: str) -> None:
        Path(output_path).write_bytes(Path(input_path).read_bytes())

    monkeypatch.setattr(VoiceGenerator, "_normalize_audio_segment", staticmethod(fake_normalize))
    monkeypatch.setattr(voice_generator, "probe_media_duration", lambda path: 1.0)

    lines = [
        SubtitleLine(start_hint=0, end_hint=1, text="Câu một"),
        SubtitleLine(start_hint=1, end_hint=2, text="Câu hai"),
    ]
    measured = generator._generate_consistent_voice_segments(lines, tmp_path, language="vi")

    assert [provider for _, provider in adapter.calls] == ["edge", "edge_retry", "edge_retry", "edge_retry"]
    assert len(measured) == 2
    assert all(path.read_bytes() == b"edge_retry" for _, path, _ in measured)


def test_timed_voiceover_caps_long_pauses_between_lines(tmp_path, monkeypatch):
    generator = VoiceGenerator()
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    silence_durations: list[float] = []

    def fake_generate_silence(output_path: Path, duration: float) -> None:
        silence_durations.append(round(duration, 3))
        output_path.write_bytes(b"silence")

    monkeypatch.setattr(VoiceGenerator, "_generate_silence", staticmethod(fake_generate_silence))

    sequence = generator._compose_timed_audio_sequence(
        measured_segments=[
            (SubtitleLine(start_hint=0, end_hint=3, text="Cau mot"), first, 1.0),
            (SubtitleLine(start_hint=5, end_hint=8, text="Cau hai"), second, 1.0),
        ],
        temp_dir=tmp_path,
        target_duration=8.0,
    )

    assert sequence[0] == first
    assert second in sequence
    assert silence_durations[0] == 0.28
    assert any("voice_timing_gap_compressed" in warning for warning in generator.warnings)


def test_subtitle_locked_voiceover_keeps_original_timing(tmp_path, monkeypatch):
    generator = VoiceGenerator()
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    silence_durations: list[float] = []
    fitted_calls: list[float] = []

    def fake_generate_silence(output_path: Path, duration: float) -> None:
        silence_durations.append(round(duration, 3))
        output_path.write_bytes(b"silence")

    def fake_fit(
        self,
        *,
        input_path: Path,
        output_path: Path,
        measured_duration: float,
        slot_duration: float,
        max_speedup: float,
    ) -> tuple[Path, float]:
        fitted_calls.append(round(slot_duration, 3))
        output_path.write_bytes(input_path.read_bytes())
        return output_path, min(measured_duration, slot_duration)

    monkeypatch.setattr(VoiceGenerator, "_generate_silence", staticmethod(fake_generate_silence))
    monkeypatch.setattr(VoiceGenerator, "_fit_audio_to_subtitle_slot", fake_fit)

    sequence = generator._compose_subtitle_locked_audio_sequence(
        measured_segments=[
            (SubtitleLine(start_hint=0, end_hint=1, text="Cau mot"), first, 0.6),
            (SubtitleLine(start_hint=5, end_hint=6, text="Cau hai"), second, 0.7),
        ],
        temp_dir=tmp_path,
        target_duration=8.0,
    )

    assert sequence
    assert silence_durations[0] == 4.4
    assert silence_durations[-1] == 2.3
    assert fitted_calls == [1.0, 1.0]
    assert [(line.start_hint, line.end_hint) for line in generator.last_subtitle_timeline] == [(0.0, 1.0), (5.0, 6.0)]


def test_subtitle_locked_chunks_do_not_redistribute_to_full_video():
    script = ProductVideoScript.model_validate(
        {
            "hook": "Hook",
            "voiceover": [
                {"time_hint": "0-3s", "text": "Cau mot"},
                {"time_hint": "7-10s", "text": "Cau hai"},
            ],
            "subtitles": [
                {"start_hint": 0, "end_hint": 3, "text": "Cau mot"},
                {"start_hint": 7, "end_hint": 10, "text": "Cau hai"},
            ],
            "cta": "Cau hai",
            "caption": "Caption",
            "hashtags": [],
        }
    )

    chunks = VoiceGenerator._subtitle_locked_chunks(script, target_duration=30.0)

    assert [(line.start_hint, line.end_hint, line.text) for line in chunks] == [
        (0.0, 3.0, "Cau mot"),
        (7.0, 10.0, "Cau hai"),
    ]


def test_subtitle_locked_voiceover_speeds_up_dense_line_without_dense_warning(tmp_path, monkeypatch):
    generator = VoiceGenerator()
    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    input_path.write_bytes(b"voice")
    filters: list[str] = []

    def fake_run_ffmpeg(args):
        filters.append(args[args.index("-af") + 1])
        output_path.write_bytes(b"fitted")

    monkeypatch.setattr(voice_generator, "run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr(voice_generator, "probe_media_duration", lambda path: 1.0)

    fitted_path, fitted_duration = generator._fit_audio_to_subtitle_slot(
        input_path=input_path,
        output_path=output_path,
        measured_duration=2.4,
        slot_duration=1.0,
        max_speedup=3.0,
    )

    assert fitted_path == output_path
    assert fitted_duration == 1.0
    assert "atempo=2.000,atempo=1.200" in filters[0]
    assert any("voice_line_speed_adjusted" in warning for warning in generator.warnings)
    assert not any("voice_line_too_dense_for_subtitle" in warning for warning in generator.warnings)


def test_global_voice_fit_speeds_up_before_trimming():
    audio_filter = VoiceGenerator._audio_trim_filter(source_duration=14.0, target_duration=10.0)

    assert audio_filter.startswith("atempo=1.400")
    assert "atrim=0:10.000" in audio_filter
