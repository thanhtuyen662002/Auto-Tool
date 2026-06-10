from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from app.adapters.ffmpeg_adapter import FFmpegError, probe_media_duration, run_ffmpeg
from app.modules.audio.audio_normalizer import normalize_audio_for_render
from app.modules.cache.cache_service import CacheService
from app.modules.script_writer.length_guard import prepare_script_for_tts
from app.modules.script_writer.script_writer import ProductVideoScript, SubtitleLine
from app.modules.script_writer.timing import build_subtitle_timeline
from app.modules.tts.text_cleanup import clean_text_for_tts
from app.modules.tts.tts_manager import TTSManager
from app.modules.tts.tts_schema import TTSResult, TTSSettings
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger


logger = get_logger(__name__)
MAX_INTER_LINE_SILENCE = 0.28


class VoiceGenerator:
    def __init__(
        self,
        tts_manager: Any | None = None,
        cache_service: CacheService | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.tts_manager = tts_manager or TTSManager()
        self.cache_service = cache_service
        self.cache_enabled = cache_enabled
        self.warnings: list[str] = []
        self.last_subtitle_timeline: list[SubtitleLine] = []
        self.last_tts_result: TTSResult | None = None
        self.last_voice_duration: float | None = None
        self.last_cache_hit = False

    def generate_voiceover(
        self,
        script: ProductVideoScript,
        output_dir: str,
        filename: str = "voiceover.wav",
        text_filename: str = "voiceover_text.txt",
        language: str = "vi",
        target_duration: float | None = None,
        tts_settings: TTSSettings | None = None,
    ) -> str:
        self.warnings = []
        self.last_subtitle_timeline = []
        self.last_tts_result = None
        self.last_voice_duration = None
        self.last_cache_hit = False
        settings = self._settings(tts_settings, language, filename)
        script, guard_warnings = prepare_script_for_tts(script, target_duration, language)
        self.warnings.extend(guard_warnings)

        target_dir = ensure_dir(output_dir)
        voice_chunks = build_subtitle_timeline(script, target_duration) if target_duration else []
        voice_text = "\n".join(
            f"[{line.start_hint:.2f}-{line.end_hint:.2f}s] {line.text}"
            for line in voice_chunks
            if line.start_hint is not None and line.end_hint is not None
        )
        if not voice_text:
            voice_text = "\n".join(line.text for line in script.voiceover)
        text_path = target_dir / text_filename
        text_path.write_text(voice_text, encoding="utf-8")

        voice_path = target_dir / filename
        cache_key = self._cache_key(voice_text, settings, target_duration)
        if cache_key and self._restore_from_cache(cache_key, voice_path):
            return str(voice_path)

        used_timed_generation = False
        if target_duration and target_duration > 0 and voice_chunks:
            used_timed_generation = True
            generated_path = self._generate_timed_voiceover(
                voice_chunks=voice_chunks,
                output_path=voice_path,
                settings=settings,
                target_duration=target_duration,
            )
        else:
            plain_voice_text = "\n".join(line.text for line in script.voiceover)
            result = self._generate_voice(plain_voice_text, voice_path, settings)
            generated_path = result.output_path

        if not used_timed_generation:
            self.warnings.extend(self._provider_warnings())
        self._read_final_voice_duration(generated_path)
        self._store_cache(cache_key, generated_path, settings)
        return generated_path

    def _generate_timed_voiceover(
        self,
        voice_chunks: list[SubtitleLine],
        output_path: Path,
        settings: TTSSettings,
        target_duration: float,
    ) -> str:
        temp_dir = ensure_dir(output_path.parent / f"_{output_path.stem}_voice_parts")

        try:
            measured_segments = self._generate_consistent_voice_segments(
                voice_chunks=voice_chunks,
                temp_dir=temp_dir,
                settings=settings,
            )

            raw_concat_path = temp_dir / "voice_concat_raw.wav"
            sequence_paths = self._compose_timed_audio_sequence(
                measured_segments=measured_segments,
                temp_dir=temp_dir,
                target_duration=target_duration,
            )
            self._concat_audio_segments(sequence_paths, raw_concat_path)
            timeline_scale = self._fit_voice_duration(str(raw_concat_path), str(output_path), target_duration)
            self._read_final_voice_duration(str(output_path))
            if self.last_tts_result is not None:
                self.last_tts_result = self.last_tts_result.model_copy(
                    update={
                        "output_path": str(output_path),
                        "duration": self.last_voice_duration,
                        "format": output_path.suffix.lower().lstrip(".") or settings.output_format,
                        "warnings": list(dict.fromkeys([*self.warnings, *self.last_tts_result.warnings])),
                    }
                )
            if timeline_scale != 1.0:
                self.last_subtitle_timeline = self._scale_timeline(
                    self.last_subtitle_timeline,
                    scale=timeline_scale,
                    target_duration=target_duration,
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return str(output_path)

    def _generate_consistent_voice_segments(
        self,
        voice_chunks: list[SubtitleLine],
        temp_dir: Path,
        settings: TTSSettings | None = None,
        language: str = "vi",
    ) -> list[tuple[SubtitleLine, Path, float]]:
        settings = settings or self._settings(None, language, "voiceover.wav")
        locked_provider: str | None = None
        self.tts_manager.lock_provider(None)

        for _attempt in range(1, 4):
            measured_segments: list[tuple[SubtitleLine, Path, float]] = []
            selected_provider: str | None = locked_provider
            should_restart = False
            self.tts_manager.lock_provider(locked_provider)
            self._clear_voice_parts(temp_dir)

            for index, line in enumerate(voice_chunks, start=1):
                raw_path = temp_dir / f"part_{index:03d}_raw.{self._temp_audio_suffix(settings)}"
                fitted_path = temp_dir / f"part_{index:03d}.wav"
                result = self._generate_voice(line.text, raw_path, settings)
                self.warnings.extend(result.warnings)
                current_provider = result.provider or "unknown"

                if selected_provider is None:
                    selected_provider = current_provider
                    self.tts_manager.lock_provider(selected_provider)
                elif current_provider != selected_provider:
                    warning = (
                        "tts_provider_changed: Nhà cung cấp TTS thay đổi trong cùng một phần đọc "
                        f"({selected_provider} -> {current_provider}); đang tạo lại toàn bộ giọng đọc bằng {current_provider}."
                    )
                    logger.warning(warning)
                    self.warnings.append(warning)
                    locked_provider = current_provider
                    should_restart = True
                    break

                self._normalize_audio_segment(result.output_path, str(fitted_path))
                Path(result.output_path).unlink(missing_ok=True)
                measured_duration = probe_media_duration(str(fitted_path))
                measured_segments.append((line, fitted_path, measured_duration))

            if not should_restart:
                return measured_segments

        raise RuntimeError("Không thể tạo giọng đọc bằng một nhà cung cấp TTS thống nhất.")

    @staticmethod
    def _clear_voice_parts(temp_dir: Path) -> None:
        for path in temp_dir.glob("part_*.*"):
            path.unlink(missing_ok=True)

    def _compose_timed_audio_sequence(
        self,
        measured_segments: list[tuple[SubtitleLine, Path, float]],
        temp_dir: Path,
        target_duration: float,
    ) -> list[Path]:
        if not measured_segments:
            return []

        sequence: list[Path] = []
        cursor = 0.0
        timeline: list[SubtitleLine] = []
        silence_index = 1

        for planned_line, audio_path, measured_duration in measured_segments:
            planned_start = float(planned_line.start_hint or cursor)
            if planned_start > cursor:
                planned_gap = planned_start - cursor
                gap_duration = min(planned_gap, MAX_INTER_LINE_SILENCE)
                if planned_gap - gap_duration > 0.35:
                    self._add_warning_once(
                        "voice_timing_gap_compressed: Khoảng nghỉ giữa các câu giọng đọc đã được rút ngắn "
                        "để nghe liền mạch hơn."
                    )
                silence_path = temp_dir / f"silence_{silence_index:03d}.wav"
                silence_index += 1
                if gap_duration > 0:
                    self._generate_silence(silence_path, gap_duration)
                    sequence.append(silence_path)
                    cursor += gap_duration

            if cursor >= target_duration:
                break

            sequence.append(audio_path)
            speech_start = cursor
            speech_end = min(target_duration, cursor + measured_duration)
            if speech_end > speech_start:
                timeline.extend(
                    self._build_display_subtitle_timeline(
                        text=planned_line.text,
                        start=speech_start,
                        end=speech_end,
                    )
                )
            cursor += measured_duration

        if cursor < target_duration:
            silence_path = temp_dir / f"silence_{silence_index:03d}.wav"
            silence_gap = max(0.0, min(0.2, target_duration - cursor))
            if silence_gap > 0:
                self._generate_silence(silence_path, silence_gap)
                sequence.append(silence_path)

        self.last_subtitle_timeline = timeline

        return sequence

    def _fit_voice_duration(self, input_path: str, output_path: str, target_duration: float) -> float:
        try:
            source_duration = probe_media_duration(input_path)
            if source_duration > target_duration > 0:
                warning = (
                    f"voice_longer_than_video: Giọng đọc ({source_duration:.3f}s) dài hơn video "
                    f"({target_duration:.3f}s), audio sẽ được cắt theo thời lượng video."
                )
                logger.warning(warning)
                self.warnings.append(warning)
            run_ffmpeg(
                [
                    "-y",
                    "-i",
                    input_path,
                    "-af",
                    self._audio_trim_filter(source_duration, target_duration),
                    "-ac",
                    "1",
                    "-ar",
                    "44100",
                    *self._audio_output_args(output_path),
                    output_path,
                ]
            )
            return 1.0
        except (Exception, FFmpegError) as exc:
            warning = f"Không thể căn thời lượng giọng đọc, đang dùng thời lượng TTS gốc. Lý do: {exc}"
            logger.warning(warning)
            self.warnings.append(warning)
            Path(input_path).replace(output_path)
            return 1.0

    @staticmethod
    def _normalize_audio_segment(input_path: str, output_path: str) -> None:
        normalize_audio_for_render(input_path, output_path, target_format="wav", sample_rate=44100)

    @staticmethod
    def _generate_silence(output_path: Path, duration: float) -> None:
        run_ffmpeg(
            [
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=44100",
                "-t",
                f"{duration:.3f}",
                "-acodec",
                "pcm_s16le",
                str(output_path),
            ]
        )

    @staticmethod
    def _concat_audio_segments(segment_paths: list[Path], output_path: Path) -> None:
        if not segment_paths:
            raise ValueError("Không thể ghép giọng đọc vì chưa tạo được đoạn audio nào.")

        concat_file = output_path.with_suffix(".concat.txt")
        concat_file.write_text(
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths) + "\n",
            encoding="utf-8",
        )
        try:
            run_ffmpeg(
                [
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    str(output_path),
                ]
            )
        finally:
            concat_file.unlink(missing_ok=True)

    @staticmethod
    def _build_display_subtitle_timeline(text: str, start: float, end: float) -> list[SubtitleLine]:
        chunks = VoiceGenerator._split_subtitle_text(text)
        duration = max(0.0, end - start)
        if not chunks or duration <= 0:
            return []

        weights = [max(1, len(chunk)) for chunk in chunks]
        total_weight = sum(weights)
        cursor = start
        timeline: list[SubtitleLine] = []
        lead_seconds = 0.08

        for index, chunk in enumerate(chunks):
            if index == len(chunks) - 1:
                chunk_end = end
            else:
                chunk_duration = duration * (weights[index] / total_weight)
                chunk_end = min(end, cursor + chunk_duration)

            display_start = max(0.0, cursor - lead_seconds)
            display_end = max(display_start + 0.25, chunk_end - lead_seconds)
            display_end = min(end, display_end)
            if display_end > display_start:
                timeline.append(
                    SubtitleLine(
                        start_hint=round(display_start, 3),
                        end_hint=round(display_end, 3),
                        text=chunk,
                    )
                )
            cursor = chunk_end

        return timeline

    @staticmethod
    def _split_subtitle_text(text: str, max_chars: int = 38) -> list[str]:
        cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        if not cleaned:
            return []

        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?…])\s+", cleaned)
            if part.strip()
        ] or [cleaned]

        chunks: list[str] = []
        for sentence in sentences:
            chunks.extend(VoiceGenerator._split_long_subtitle(sentence, max_chars=max_chars))
        return chunks

    @staticmethod
    def _split_long_subtitle(text: str, max_chars: int) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        pieces = [
            piece.strip()
            for piece in re.split(r"(?<=[,;:])\s+|\s+(?=và|nhưng|nên|giúp|để|khi|nếu)\s*", text, flags=re.IGNORECASE)
            if piece.strip()
        ]
        chunks: list[str] = []
        current = ""

        for piece in pieces:
            candidate = f"{current} {piece}".strip() if current else piece
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.extend(VoiceGenerator._split_words(current, max_chars=max_chars))
            current = piece

        if current:
            chunks.extend(VoiceGenerator._split_words(current, max_chars=max_chars))

        return chunks or [text]

    @staticmethod
    def _split_words(text: str, max_chars: int) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []

        for word in words:
            candidate = " ".join([*current, word])
            if current and len(candidate) > max_chars:
                chunks.append(" ".join(current))
                current = [word]
            else:
                current.append(word)

        if current:
            chunks.append(" ".join(current))
        return chunks

    @staticmethod
    def _scale_timeline(
        lines: list[SubtitleLine],
        scale: float,
        target_duration: float,
    ) -> list[SubtitleLine]:
        scaled: list[SubtitleLine] = []
        for line in lines:
            start = max(0.0, min(target_duration, float(line.start_hint or 0.0) * scale))
            end = max(0.0, min(target_duration, float(line.end_hint or 0.0) * scale))
            if end > start:
                scaled.append(
                    SubtitleLine(
                        start_hint=round(start, 3),
                        end_hint=round(end, 3),
                        text=line.text,
                    )
                )
        return scaled

    @staticmethod
    def _audio_trim_filter(source_duration: float, target_duration: float) -> str:
        if source_duration <= 0 or target_duration <= 0:
            return "asetpts=PTS-STARTPTS"

        if source_duration > target_duration:
            return f"atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS"
        return "asetpts=PTS-STARTPTS"

    def _generate_voice(self, text: str, output_path: Path, settings: TTSSettings) -> TTSResult:
        cleaned_text = clean_text_for_tts(text)
        if not cleaned_text:
            raise ValueError("TTS text is empty after cleanup.")
        result = self.tts_manager.generate_voice(cleaned_text, str(output_path), settings)
        if isinstance(result, TTSResult):
            self.last_tts_result = result
            return result

        provider = getattr(self.tts_manager, "last_provider", None) or "unknown"
        warnings = list(getattr(self.tts_manager, "warnings", []))
        duration = probe_media_duration(str(result))
        tts_result = TTSResult(
            provider=provider,
            output_path=str(result),
            duration=round(duration, 3),
            format=Path(result).suffix.lower().lstrip(".") or settings.output_format,
            success=True,
            warnings=warnings,
        )
        self.last_tts_result = tts_result
        return tts_result

    def _cache_key(self, voice_text: str, settings: TTSSettings, target_duration: float | None) -> str | None:
        if not self.cache_service or not self.cache_service.enabled or not self.cache_enabled:
            return None
        return self.cache_service.keys.build_tts_key(
            voice_text,
            settings.voice,
            settings.provider,
            settings.rate,
            pitch=settings.pitch,
            volume=settings.volume,
            output_format=settings.output_format,
            target_duration=target_duration,
        )

    def _restore_from_cache(self, cache_key: str, voice_path: Path) -> bool:
        if not self.cache_service:
            return False
        cached = self.cache_service.get_json("tts", cache_key)
        if not cached:
            return False
        cached_path = cached.get("cached_path")
        if not cached_path or not Path(str(cached_path)).exists():
            return False
        try:
            shutil.copy2(str(cached_path), voice_path)
            timeline = cached.get("subtitle_timeline") or []
            self.last_subtitle_timeline = [SubtitleLine.model_validate(item) for item in timeline]
            result_payload = cached.get("tts_result")
            if isinstance(result_payload, dict):
                self.last_tts_result = TTSResult.model_validate(result_payload).model_copy(
                    update={"output_path": str(voice_path)}
                )
            self._read_final_voice_duration(str(voice_path))
            if self.last_tts_result is not None:
                self.last_tts_result = self.last_tts_result.model_copy(
                    update={"output_path": str(voice_path), "duration": self.last_voice_duration}
                )
            self.last_cache_hit = True
            return True
        except Exception as exc:
            logger.warning("Không thể dùng TTS cache, sẽ tạo lại: %s", exc)
            return False

    def _store_cache(self, cache_key: str | None, generated_path: str, settings: TTSSettings) -> None:
        if not cache_key or not self.cache_service:
            return
        cached_path = self.cache_service.set_file(cache_key, generated_path)
        if not cached_path:
            return
        result = self.last_tts_result
        if result is None:
            result = TTSResult(
                provider=settings.provider,
                output_path=generated_path,
                duration=self.last_voice_duration,
                format=Path(generated_path).suffix.lower().lstrip(".") or settings.output_format,
                success=True,
                warnings=list(self.warnings),
            )
        self.cache_service.set_json(
            cache_key,
            {
                "cached_path": cached_path,
                "tts_result": result.model_dump(mode="json"),
                "voice_duration": self.last_voice_duration,
                "subtitle_timeline": [line.model_dump(mode="json") for line in self.last_subtitle_timeline],
            },
        )

    def _provider_warnings(self) -> list[str]:
        if self.last_tts_result is not None:
            return self.last_tts_result.warnings
        return list(getattr(self.tts_manager, "warnings", []))

    def _read_final_voice_duration(self, output_path: str) -> None:
        try:
            self.last_voice_duration = round(probe_media_duration(output_path), 3)
        except Exception as exc:
            warning = f"Không thể đọc thời lượng giọng đọc đã tạo: {exc}"
            logger.warning(warning)
            self.warnings.append(warning)

    def _add_warning_once(self, warning: str) -> None:
        if warning and warning not in self.warnings:
            self.warnings.append(warning)

    @staticmethod
    def _settings(tts_settings: TTSSettings | None, language: str, filename: str) -> TTSSettings:
        settings = tts_settings or TTSSettings()
        output_format = Path(filename).suffix.lower().lstrip(".") or settings.output_format
        return settings.model_copy(update={"language": settings.language or language, "output_format": output_format})

    @staticmethod
    def _temp_audio_suffix(settings: TTSSettings) -> str:
        provider = settings.provider.strip().lower().replace("-", "_")
        if provider in {"edge", "edge_tts", "gtts", "google", "google_tts"}:
            return "mp3"
        return "wav"

    @staticmethod
    def _audio_output_args(output_path: str) -> list[str]:
        suffix = Path(output_path).suffix.lower()
        if suffix == ".mp3":
            return ["-c:a", "libmp3lame", "-b:a", "128k"]
        return ["-acodec", "pcm_s16le"]
