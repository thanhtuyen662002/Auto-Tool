from __future__ import annotations

from pathlib import Path

from app.modules.script_writer.script_writer import SubtitleLine
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
