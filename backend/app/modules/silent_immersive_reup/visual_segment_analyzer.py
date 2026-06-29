from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.douyin_schema import DouyinReupSettings
from app.modules.silent_immersive_reup.silent_schema import SilentVisualSegment
from app.utils.file_utils import ensure_dir


class VisualSegmentAnalyzer:
    def analyze_video(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        output_dir: str,
    ) -> list[SilentVisualSegment]:
        target_dir = ensure_dir(output_dir)
        frames_dir = ensure_dir(target_dir / "frames")
        segments = self._analyze_with_cv2(video_path, settings, frames_dir)
        if not segments:
            segments = self._fallback_segments(video_path, settings)

        report_path = target_dir / f"{Path(video_path).stem}_silent_segments.json"
        report_path.write_text(
            json.dumps([segment.model_dump(mode="json") for segment in segments], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return segments

    def _analyze_with_cv2(
        self,
        video_path: str,
        settings: DouyinReupSettings,
        frames_dir: Path,
    ) -> list[SilentVisualSegment]:
        try:
            import cv2
            import numpy as np
        except Exception:
            return []

        capture = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(str(video_path))
            if not capture.isOpened():
                capture.release()
                return []
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 30.0
            frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frame_count / fps if frame_count > 0 else probe_video(video_path).duration
            if duration <= 0:
                return []

            sample_step = 0.5 if duration <= 20 else 1.0
            samples: list[dict] = []
            previous_gray = None
            timestamp = 0.0
            while timestamp <= duration:
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, frame = capture.read()
                if not ok or frame is None:
                    timestamp += sample_step
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(gray.mean())
                sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                motion = 0.0
                if previous_gray is not None:
                    motion = float(np.mean(cv2.absdiff(gray, previous_gray)))
                samples.append(
                    {
                        "time": timestamp,
                        "frame": frame.copy(),
                        "brightness_score": _brightness_score(brightness),
                        "sharpness_score": min(1.0, sharpness / 500.0),
                        "motion_score": min(1.0, motion / 45.0),
                        "diff": motion,
                    }
                )
                previous_gray = gray
                timestamp += sample_step

            if not samples:
                return []

            min_duration = settings.silent_segment_duration_min
            max_duration = settings.silent_segment_duration_max
            boundaries = [0.0]
            segment_start = 0.0
            for sample in samples[1:]:
                elapsed = sample["time"] - segment_start
                scene_change = sample["diff"] >= 28.0 and elapsed >= min_duration
                too_long = elapsed >= max_duration
                if scene_change or too_long:
                    boundaries.append(round(sample["time"], 3))
                    segment_start = sample["time"]
            if boundaries[-1] < duration:
                boundaries.append(round(duration, 3))

            segments: list[SilentVisualSegment] = []
            for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
                if end - start < min_duration * 0.75:
                    continue
                window = [sample for sample in samples if start <= sample["time"] <= end] or [min(samples, key=lambda item: abs(item["time"] - ((start + end) / 2)))]
                mid_sample = min(window, key=lambda item: abs(item["time"] - ((start + end) / 2)))
                frame_path = frames_dir / f"frame_seg_{index:03d}.jpg"
                frame_written = _write_cv2_frame(frame_path, mid_sample["frame"])
                motion_score = mean(sample["motion_score"] for sample in window)
                sharpness_score = mean(sample["sharpness_score"] for sample in window)
                brightness_score = mean(sample["brightness_score"] for sample in window)
                visual_score = _clamp01((sharpness_score * 0.45) + (brightness_score * 0.25) + (motion_score * 0.30))
                segment_warnings = [] if frame_written else ["Không ghi được frame đại diện để gửi AI vision."]
                segments.append(
                    SilentVisualSegment(
                        id=f"seg_{index:03d}",
                        video_path=str(video_path),
                        start=round(start, 3),
                        end=round(end, 3),
                        duration=round(end - start, 3),
                        visual_score=round(visual_score, 4),
                        motion_score=round(motion_score, 4),
                        sharpness_score=round(sharpness_score, 4),
                        brightness_score=round(brightness_score, 4),
                        representative_frame_path=str(frame_path) if frame_written else None,
                        warnings=segment_warnings,
                    )
                )
            return segments
        finally:
            capture.release()

    @staticmethod
    def _fallback_segments(video_path: str, settings: DouyinReupSettings) -> list[SilentVisualSegment]:
        media = probe_video(video_path)
        max_duration = max(settings.silent_segment_duration_min, settings.silent_segment_duration_max)
        segments: list[SilentVisualSegment] = []
        cursor = 0.0
        index = 1
        while cursor < media.duration:
            end = min(media.duration, cursor + max_duration)
            if end - cursor < 0.6 and segments:
                previous = segments[-1]
                segments[-1] = previous.model_copy(
                    update={"end": round(media.duration, 3), "duration": round(media.duration - previous.start, 3)}
                )
                break
            segments.append(
                SilentVisualSegment(
                    id=f"seg_{index:03d}",
                    video_path=str(video_path),
                    start=round(cursor, 3),
                    end=round(end, 3),
                    duration=round(end - cursor, 3),
                    visual_score=0.5,
                    warnings=["Không phân tích được frame bằng OpenCV, đã chia segment đều theo duration."],
                )
            )
            cursor = end
            index += 1
        return segments


def _brightness_score(value: float) -> float:
    return _clamp01(1.0 - abs(value - 128.0) / 128.0)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _write_cv2_frame(target: Path, frame) -> bool:
    try:
        import cv2
    except Exception:
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not ok:
            return False
        target.write_bytes(encoded.tobytes())
        return target.exists() and target.stat().st_size > 0
    except Exception:
        return False
