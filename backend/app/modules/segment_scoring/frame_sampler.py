from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.logger import get_logger

if TYPE_CHECKING:
    import numpy as np


logger = get_logger(__name__)


class FrameSampler:
    def sample_frames(
        self,
        video_path: str,
        start: float,
        end: float,
        max_frames: int = 5,
    ) -> list["np.ndarray"]:
        if max_frames <= 0 or end <= start:
            return []

        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV is not installed; cannot score video frames.")
            return []

        capture = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(video_path)
            if not capture.isOpened():
                capture.release()
                logger.warning("Could not open video for frame sampling: %s", video_path)
                return []

        frames: list["np.ndarray"] = []
        try:
            sample_count = max(1, min(max_frames, int(max_frames)))
            duration = end - start
            if sample_count == 1:
                timestamps = [start + duration / 2]
            else:
                step = duration / (sample_count + 1)
                timestamps = [start + step * (index + 1) for index in range(sample_count)]

            for timestamp in timestamps:
                capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp) * 1000)
                ok, frame = capture.read()
                if ok and frame is not None:
                    frames.append(frame)

            if not frames:
                logger.warning(
                    "Could not read frames for segment: %s %.3f-%.3f",
                    video_path,
                    start,
                    end,
                )
            return frames
        except Exception as exc:
            logger.warning(
                "Frame sampling failed for %s %.3f-%.3f: %s",
                video_path,
                start,
                end,
                exc,
            )
            return []
        finally:
            capture.release()

