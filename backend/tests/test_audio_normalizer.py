from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.ffmpeg_adapter import FFmpegError, MissingFFmpegError, probe_media_duration, run_ffmpeg
from app.modules.audio.audio_normalizer import normalize_audio_for_render


def test_mp3_provider_output_is_normalized_to_wav(tmp_path):
    mp3_path = tmp_path / "provider_voice.mp3"
    wav_path = tmp_path / "normalized_voice.wav"
    try:
        run_ffmpeg(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=900:duration=1.200",
                "-ac",
                "1",
                "-ar",
                "44100",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "96k",
                str(mp3_path),
            ]
        )
    except (MissingFFmpegError, FFmpegError) as exc:
        pytest.skip(f"FFmpeg is required for audio normalization tests: {exc}")

    output = normalize_audio_for_render(str(mp3_path), str(wav_path), target_format="wav")

    assert output.endswith(".wav")
    assert Path(output).exists()
    assert probe_media_duration(output) > 1.0
