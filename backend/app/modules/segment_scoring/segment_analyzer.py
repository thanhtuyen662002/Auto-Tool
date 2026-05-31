from __future__ import annotations

from typing import Any

import numpy as np


class SegmentAnalyzer:
    def analyze_frames(self, frames: list[np.ndarray]) -> dict[str, Any]:
        if not frames:
            return {
                "frame_count": 0,
                "brightness_mean": 0.0,
                "sharpness_laplacian_var": 0.0,
                "motion_mean": 0.0,
                "brightness_score": 0.0,
                "sharpness_score": 0.0,
                "motion_score": 0.0,
                "freeze_score": 0.0,
                "stability_score": 0.0,
            }

        gray_frames = [self._to_gray(frame) for frame in frames]
        brightness_mean = float(np.mean([np.mean(frame) for frame in gray_frames]))
        sharpness_value = float(np.mean([self._laplacian_variance(frame) for frame in gray_frames]))
        motion_value = self._motion_mean(gray_frames)

        return {
            "frame_count": len(gray_frames),
            "brightness_mean": round(brightness_mean, 3),
            "sharpness_laplacian_var": round(sharpness_value, 3),
            "motion_mean": round(motion_value, 3),
            "brightness_score": round(self._brightness_score(brightness_mean), 3),
            "sharpness_score": round(self._sharpness_score(sharpness_value), 3),
            "motion_score": round(self._motion_score(motion_value), 3),
            "freeze_score": round(self._freeze_score(motion_value), 3),
            "stability_score": round(self._stability_score(motion_value), 3),
        }

    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return frame.astype(np.float32)
        if frame.ndim == 3 and frame.shape[2] >= 3:
            channels = frame.astype(np.float32)
            return channels[:, :, 0] * 0.114 + channels[:, :, 1] * 0.587 + channels[:, :, 2] * 0.299
        return frame.astype(np.float32)

    @staticmethod
    def _laplacian_variance(gray: np.ndarray) -> float:
        center = gray[1:-1, 1:-1] * -4
        laplacian = center + gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
        if laplacian.size == 0:
            return 0.0
        return float(np.var(laplacian))

    @staticmethod
    def _motion_mean(gray_frames: list[np.ndarray]) -> float:
        if len(gray_frames) < 2:
            return 0.0

        diffs: list[float] = []
        for previous, current in zip(gray_frames, gray_frames[1:]):
            if previous.shape != current.shape:
                continue
            diffs.append(float(np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))))
        return float(np.mean(diffs)) if diffs else 0.0

    @staticmethod
    def _brightness_score(mean: float) -> float:
        if mean < 35:
            return _clamp(mean / 35 * 0.2)
        if mean < 60:
            return _scale(mean, 35, 60, 0.25, 0.7)
        if mean <= 190:
            return 1.0
        if mean <= 235:
            return _scale(mean, 190, 235, 0.85, 0.35)
        return max(0.0, _scale(mean, 235, 255, 0.2, 0.0))

    @staticmethod
    def _sharpness_score(laplacian_var: float) -> float:
        if laplacian_var < 40:
            return _clamp(laplacian_var / 40 * 0.2)
        if laplacian_var < 80:
            return _scale(laplacian_var, 40, 80, 0.3, 0.6)
        if laplacian_var <= 300:
            return _scale(laplacian_var, 80, 300, 0.65, 0.9)
        return 1.0

    @staticmethod
    def _motion_score(motion: float) -> float:
        if motion < 2:
            return _clamp(motion / 2 * 0.2)
        if motion < 8:
            return _scale(motion, 2, 8, 0.35, 0.85)
        if motion <= 35:
            return 1.0
        if motion <= 70:
            return _scale(motion, 35, 70, 0.9, 0.45)
        return max(0.1, _scale(motion, 70, 120, 0.4, 0.1))

    @staticmethod
    def _freeze_score(motion: float) -> float:
        if motion < 1:
            return 0.0
        if motion < 4:
            return _scale(motion, 1, 4, 0.2, 0.7)
        if motion < 8:
            return _scale(motion, 4, 8, 0.75, 1.0)
        return 1.0

    @staticmethod
    def _stability_score(motion: float) -> float:
        if motion <= 20:
            return 1.0
        if motion <= 50:
            return _scale(motion, 20, 50, 1.0, 0.6)
        if motion <= 90:
            return _scale(motion, 50, 90, 0.55, 0.25)
        return 0.15


def _scale(value: float, low: float, high: float, out_low: float, out_high: float) -> float:
    if high <= low:
        return _clamp(out_low)
    ratio = (value - low) / (high - low)
    return _clamp(out_low + ratio * (out_high - out_low))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

