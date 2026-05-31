from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_media_duration, run_ffmpeg
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)


def normalize_audio_for_render(
    input_path: str,
    output_path: str,
    target_format: str = "wav",
    sample_rate: int = 44100,
) -> str:
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Audio input does not exist: {source}")

    target = Path(output_path).expanduser().resolve()
    target_format = target_format.strip().lower().lstrip(".") or "wav"
    if target.suffix.lower() != f".{target_format}":
        target = target.with_suffix(f".{target_format}")
    ensure_dir(target.parent)
    target.unlink(missing_ok=True)

    source_duration = probe_media_duration(str(source))
    logger.info(
        "Normalizing audio for render: input=%s output=%s duration=%.3fs sample_rate=%s",
        source,
        target,
        source_duration,
        sample_rate,
    )

    args = [
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
    ]
    if target_format == "wav":
        args.extend(["-acodec", "pcm_s16le"])
    elif target_format == "mp3":
        args.extend(["-c:a", "libmp3lame", "-b:a", "128k"])
    else:
        raise ValueError(f"Unsupported normalized audio format: {target_format}")
    args.append(str(target))
    run_ffmpeg(args)

    normalized_duration = probe_media_duration(str(target))
    logger.info(
        "Normalized audio ready: output=%s duration=%.3fs",
        target,
        normalized_duration,
    )
    return str(target)


def create_silent_audio(output_path: str, duration: float, sample_rate: int = 44100) -> str:
    target = Path(output_path).expanduser().resolve()
    ensure_dir(target.parent)
    target.unlink(missing_ok=True)
    duration = max(0.1, float(duration))

    args = [
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
        "-t",
        f"{duration:.3f}",
    ]
    if target.suffix.lower() == ".mp3":
        args.extend(["-c:a", "libmp3lame", "-b:a", "96k"])
    else:
        args.extend(["-acodec", "pcm_s16le"])
    args.append(str(target))
    run_ffmpeg(args)
    return str(target)
