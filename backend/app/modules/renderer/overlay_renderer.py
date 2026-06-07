from __future__ import annotations

from pathlib import Path

from app.adapters.ffmpeg_adapter import FFmpegError, probe_media_duration, probe_video, run_ffmpeg
from app.modules.cache.cache_service import CacheService
from app.modules.script_writer.script_writer import ProductVideoScript
from app.modules.visual_style.overlay_asset_builder import build_overlay_asset
from app.modules.visual_style.visual_style_service import VisualStyleService
from app.schemas.project_schema import ProjectConfig
from app.utils.logger import get_logger


logger = get_logger(__name__)
VOICE_MIX_GAIN = 1.7


class OverlayRenderer:
    def __init__(self, cache_service: CacheService | None = None, cache_enabled: bool = True) -> None:
        self.cache_service = cache_service
        self.cache_enabled = cache_enabled
        self.warnings: list[str] = []
        self.last_visual_style: dict = {}
        self.last_overlay_cache_hit = False

    def render_final_video(
        self,
        visual_video_path: str,
        voice_path: str,
        subtitle_path: str,
        script: ProductVideoScript,
        config: ProjectConfig,
        output_path: str,
        music_path: str | None = None,
        fallback_subtitle_path: str | None = None,
    ) -> str:
        self.warnings = []
        self.last_visual_style = {}
        self.last_overlay_cache_hit = False
        visual_info = probe_video(visual_video_path)
        duration = visual_info.duration
        voice_duration = probe_media_duration(voice_path)
        if voice_duration - duration > 1.0:
            warning = "voice_longer_than_video: Giọng đọc sẽ được cắt theo thời lượng video khi render cuối."
            logger.warning(warning)
            self.warnings.append(warning)
        elif duration - voice_duration > 2.0:
            warning = "voice_shorter_than_video: Phần cuối video sẽ giữ im lặng vì giọng đọc ngắn hơn video."
            logger.warning(warning)
            self.warnings.append(warning)

        preset = VisualStyleService().resolve_preset(config.visual_style)
        overlay_asset_path = str(Path(output_path).with_name(f"{Path(output_path).stem}_overlay.png"))
        self.last_visual_style = {
            "preset_id": preset.id,
            "overlay_asset": overlay_asset_path,
            "subtitle_format": "ass" if Path(subtitle_path).suffix.lower() == ".ass" else "srt",
            "ass_subtitle_path": subtitle_path if Path(subtitle_path).suffix.lower() == ".ass" else None,
            "fallback_used": False,
            "warnings": [],
        }

        try:
            self._build_or_restore_overlay_asset(
                preset_id=preset.id,
                width=visual_info.width,
                height=visual_info.height,
                output_path=overlay_asset_path,
                build_action=lambda: build_overlay_asset(preset, visual_info.width, visual_info.height, overlay_asset_path),
                custom_overrides=config.visual_style.custom_overrides,
            )
            self._render_with_overlay_asset(
                visual_video_path=visual_video_path,
                overlay_asset_path=overlay_asset_path,
                voice_path=voice_path,
                subtitle_path=subtitle_path,
                config=config,
                output_path=output_path,
                duration=duration,
                voice_duration=voice_duration,
                include_subtitles=True,
                music_path=music_path,
            )
            return output_path
        except Exception as exc:
            warning_code = (
                "ass_subtitle_failed_fallback_to_srt"
                if isinstance(exc, FFmpegError)
                else "overlay_asset_failed_fallback_to_drawbox"
            )
            warning = f"{warning_code}: Không render được style overlay/subtitle, sẽ dùng fallback an toàn. Lý do: {exc}"
            logger.warning(warning)
            self.warnings.append(warning)
            self.last_visual_style["fallback_used"] = True
            self.last_visual_style["warnings"].append(warning_code)

        if fallback_subtitle_path:
            try:
                self._render_with_filters(
                    visual_video_path=visual_video_path,
                    voice_path=voice_path,
                    subtitle_path=fallback_subtitle_path,
                    config=config,
                    output_path=output_path,
                    duration=duration,
                    voice_duration=voice_duration,
                    include_subtitles=True,
                    music_path=music_path,
                )
                self.last_visual_style["subtitle_format"] = "srt"
                return output_path
            except FFmpegError as exc:
                warning = f"subtitle_burn_failed: Không burn được phụ đề SRT fallback, sẽ render không có phụ đề. Lý do: {exc}"
                logger.warning(warning)
                self.warnings.append(warning)
                self.last_visual_style["subtitle_format"] = "none"
                self.last_visual_style["warnings"].append("srt_subtitle_failed")

        try:
            self._render_with_filters(
                visual_video_path=visual_video_path,
                voice_path=voice_path,
                subtitle_path=subtitle_path,
                config=config,
                output_path=output_path,
                duration=duration,
                voice_duration=voice_duration,
                include_subtitles=True,
                music_path=music_path,
            )
        except FFmpegError as exc:
            warning = f"subtitle_burn_failed: Không burn được phụ đề, đã render bản dự phòng không có phụ đề. Lý do: {exc}"
            logger.warning(warning)
            self.warnings.append(warning)
            self.last_visual_style["subtitle_format"] = "none"
            self.last_visual_style["warnings"].append("subtitle_burn_failed")
            self._render_with_filters(
                visual_video_path=visual_video_path,
                voice_path=voice_path,
                subtitle_path=subtitle_path,
                config=config,
                output_path=output_path,
                duration=duration,
                voice_duration=voice_duration,
                include_subtitles=False,
                music_path=music_path,
            )

        return output_path

    def _build_or_restore_overlay_asset(
        self,
        preset_id: str,
        width: int,
        height: int,
        output_path: str,
        build_action,
        custom_overrides: dict | None,
    ) -> str:
        cache_key = None
        if self.cache_service and self.cache_service.enabled and self.cache_enabled:
            cache_key = self.cache_service.keys.build_overlay_key(
                preset_id,
                f"{width}x{height}",
                custom_overrides_hash=self.cache_service.settings_hash(custom_overrides or {}),
            )
            cached = self.cache_service.get_file("overlays", cache_key, output_path)
            if cached:
                self.last_overlay_cache_hit = True
                return cached

        result = build_action()
        if cache_key and self.cache_service:
            self.cache_service.set_file(cache_key, result)
        return result

    def _render_with_overlay_asset(
        self,
        visual_video_path: str,
        overlay_asset_path: str,
        voice_path: str,
        subtitle_path: str,
        config: ProjectConfig,
        output_path: str,
        duration: float,
        voice_duration: float,
        include_subtitles: bool,
        music_path: str | None,
    ) -> None:
        video_chain = "[0:v][1:v]overlay=0:0[vbase]"
        if include_subtitles:
            subtitle_filter = self._subtitle_filter(subtitle_path, config.effects.subtitle_size)
            video_chain = f"{video_chain};[vbase]{subtitle_filter}[vout]"
        else:
            video_chain = f"{video_chain};[vbase]null[vout]"

        if music_path:
            self._run_ffmpeg_with_overlay_and_music(
                visual_video_path=visual_video_path,
                overlay_asset_path=overlay_asset_path,
                voice_path=voice_path,
                music_path=music_path,
                output_path=output_path,
                video_chain=video_chain,
                voice_duration=voice_duration,
                duration=duration,
                config=config,
            )
            return

        audio_filter = f"[2:a]{self._voice_filter(voice_duration, duration)}[aout]"
        run_ffmpeg(
            [
                "-y",
                "-i",
                visual_video_path,
                "-i",
                overlay_asset_path,
                "-i",
                voice_path,
                "-filter_complex",
                f"{video_chain};{audio_filter}",
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(output_path),
            ]
        )

    def _render_with_filters(
        self,
        visual_video_path: str,
        voice_path: str,
        subtitle_path: str,
        config: ProjectConfig,
        output_path: str,
        duration: float,
        voice_duration: float,
        include_subtitles: bool,
        music_path: str | None,
    ) -> None:
        overlay_fraction = max(0.10, min(0.45, config.effects.overlay_height / 100.0))
        overlay_y = 1.0 - overlay_fraction
        filters = [
            f"drawbox=x=0:y=ih*{overlay_y:.4f}:w=iw:h=ih*{overlay_fraction:.4f}:color=black@0.55:t=fill"
        ]

        if include_subtitles:
            filters.append(self._subtitle_filter(subtitle_path, config.effects.subtitle_size))

        if music_path:
            self._run_ffmpeg_with_music(
                visual_video_path=visual_video_path,
                voice_path=voice_path,
                music_path=music_path,
                output_path=output_path,
                video_filters=",".join(filters),
                voice_duration=voice_duration,
                duration=duration,
                config=config,
            )
            return

        run_ffmpeg(
            [
                "-y",
                "-i",
                visual_video_path,
                "-i",
                voice_path,
                "-vf",
                ",".join(filters),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-af",
                self._voice_filter(voice_duration, duration),
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(output_path),
            ]
        )

    def _run_ffmpeg_with_music(
        self,
        visual_video_path: str,
        voice_path: str,
        music_path: str,
        output_path: str,
        video_filters: str,
        voice_duration: float,
        duration: float,
        config: ProjectConfig,
    ) -> None:
        fade_out_duration = min(config.music.fade_out, max(0.0, duration / 3.0))
        fade_out_start = max(0.0, duration - fade_out_duration)
        fade_in_duration = min(config.music.fade_in, max(0.0, duration / 3.0))
        music_volume = max(0.0, min(1.0, config.music.volume))

        music_filter = (
            f"[2:a]volume={music_volume:.4f},"
            f"afade=t=in:st=0:d={fade_in_duration:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_duration:.3f},"
            f"apad,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[music]"
        )

        if config.music.duck_under_voice:
            audio_filter = (
                f"[1:a]{self._voice_filter(voice_duration, duration)},asplit=2[voice_for_duck][voice_for_mix];"
                f"{music_filter};"
                "[music][voice_for_duck]sidechaincompress=threshold=0.040:ratio=8:attack=20:release=350[music_ducked];"
                "[voice_for_mix][music_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95[aout]"
            )
        else:
            audio_filter = (
                f"[1:a]{self._voice_filter(voice_duration, duration)}[voice];"
                f"{music_filter};"
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95[aout]"
            )
        filter_complex = f"[0:v]{video_filters}[vout];{audio_filter}"

        run_ffmpeg(
            [
                "-y",
                "-i",
                visual_video_path,
                "-i",
                voice_path,
                "-stream_loop",
                "-1",
                "-i",
                music_path,
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(output_path),
            ]
        )

    def _run_ffmpeg_with_overlay_and_music(
        self,
        visual_video_path: str,
        overlay_asset_path: str,
        voice_path: str,
        music_path: str,
        output_path: str,
        video_chain: str,
        voice_duration: float,
        duration: float,
        config: ProjectConfig,
    ) -> None:
        fade_out_duration = min(config.music.fade_out, max(0.0, duration / 3.0))
        fade_out_start = max(0.0, duration - fade_out_duration)
        fade_in_duration = min(config.music.fade_in, max(0.0, duration / 3.0))
        music_volume = max(0.0, min(1.0, config.music.volume))
        music_filter = (
            f"[3:a]volume={music_volume:.4f},"
            f"afade=t=in:st=0:d={fade_in_duration:.3f},"
            f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_duration:.3f},"
            f"apad,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[music]"
        )

        if config.music.duck_under_voice:
            audio_filter = (
                f"[2:a]{self._voice_filter(voice_duration, duration)},asplit=2[voice_for_duck][voice_for_mix];"
                f"{music_filter};"
                "[music][voice_for_duck]sidechaincompress=threshold=0.040:ratio=8:attack=20:release=350[music_ducked];"
                "[voice_for_mix][music_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95[aout]"
            )
        else:
            audio_filter = (
                f"[2:a]{self._voice_filter(voice_duration, duration)}[voice];"
                f"{music_filter};"
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                "alimiter=limit=0.95[aout]"
            )

        run_ffmpeg(
            [
                "-y",
                "-i",
                visual_video_path,
                "-i",
                overlay_asset_path,
                "-i",
                voice_path,
                "-stream_loop",
                "-1",
                "-i",
                music_path,
                "-filter_complex",
                f"{video_chain};{audio_filter}",
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(output_path),
            ]
        )

    @staticmethod
    def _subtitle_filter(subtitle_path: str, subtitle_size: int) -> str:
        escaped_path = OverlayRenderer._escape_filter_path(subtitle_path)
        if Path(subtitle_path).suffix.lower() == ".ass":
            return f"ass='{escaped_path}'"

        size = max(18, min(28, subtitle_size))
        style = (
            "FontName=Arial,"
            f"Fontsize={size},"
            "Alignment=2,"
            "MarginV=70,"
            "PrimaryColour=&H00FFFFFF&,"
            "OutlineColour=&H00101010&,"
            "BorderStyle=1,"
            "Outline=2,"
            "Shadow=0"
        )
        return f"subtitles='{escaped_path}':force_style='{style}'"

    @staticmethod
    def _audio_fit_filter(source_duration: float, target_duration: float) -> str:
        if source_duration <= 0 or target_duration <= 0:
            return f"apad,atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS"
        if source_duration > target_duration:
            return f"atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS"
        return f"apad,atrim=0:{target_duration:.3f},asetpts=PTS-STARTPTS"

    @staticmethod
    def _voice_filter(source_duration: float, target_duration: float) -> str:
        return f"{OverlayRenderer._audio_fit_filter(source_duration, target_duration)},volume={VOICE_MIX_GAIN:.2f},alimiter=limit=0.95"

    @staticmethod
    def _escape_filter_path(path: str) -> str:
        normalized = str(Path(path).resolve()).replace("\\", "/")
        return normalized.replace(":", "\\:").replace("'", "\\'")
