from __future__ import annotations

from typing import Any


class FrameSaliencyAnalyzer:
    def analyze_frame(self, frame: "Any", grid_size: int = 3) -> dict[str, Any]:
        import numpy as np

        if frame is None:
            raise ValueError("frame is required")
        if grid_size <= 0:
            raise ValueError("grid_size must be positive")

        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            edges = cv2.Canny(gray, 80, 160)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            contrast_map = np.abs(lap)
        except Exception:
            gray = frame.mean(axis=2) if len(frame.shape) == 3 else frame
            grad_y, grad_x = np.gradient(gray.astype("float32"))
            edges = (np.sqrt(grad_x ** 2 + grad_y ** 2) > 24).astype("float32")
            contrast_map = np.abs(grad_x) + np.abs(grad_y)

        gray = gray.astype("float32")
        edges = edges.astype("float32")
        contrast_map = contrast_map.astype("float32")
        height, width = gray.shape[:2]
        scores = np.zeros((grid_size, grid_size), dtype="float32")

        for row in range(grid_size):
            for col in range(grid_size):
                y0 = int(row * height / grid_size)
                y1 = int((row + 1) * height / grid_size)
                x0 = int(col * width / grid_size)
                x1 = int((col + 1) * width / grid_size)
                edge_density = float((edges[y0:y1, x0:x1] > 0).mean())
                contrast_score = _normalize(float(contrast_map[y0:y1, x0:x1].mean()), 0, 80)
                brightness = float(gray[y0:y1, x0:x1].mean()) / 255.0
                brightness_score = 1.0 - abs(brightness - 0.55) / 0.55
                center_weight = _center_weight(row, col, grid_size)
                scores[row, col] = max(
                    0.0,
                    min(
                        1.0,
                        edge_density * 0.40
                        + contrast_score * 0.25
                        + brightness_score * 0.15
                        + center_weight * 0.20,
                    ),
                )

        total = float(scores.sum()) or 1.0
        xs = []
        ys = []
        weights = []
        for row in range(grid_size):
            for col in range(grid_size):
                xs.append((col + 0.5) / grid_size)
                ys.append((row + 0.5) / grid_size)
                weights.append(float(scores[row, col]))
        weights_array = np.array(weights, dtype="float32")
        center_x = float(np.dot(np.array(xs), weights_array) / total)
        center_y = float(np.dot(np.array(ys), weights_array) / total)
        return {
            "grid": scores.tolist(),
            "center_x": center_x,
            "center_y": center_y,
            "left_edge_score": float(scores[:, 0].mean()),
            "right_edge_score": float(scores[:, -1].mean()),
            "bottom_score": float(scores[-1, :].mean()),
            "center_score": float(scores[grid_size // 2, grid_size // 2]),
            "total_score": float(scores.mean()),
        }


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _center_weight(row: int, col: int, grid_size: int) -> float:
    center = (grid_size - 1) / 2
    distance = ((row - center) ** 2 + (col - center) ** 2) ** 0.5
    max_distance = (2 * center ** 2) ** 0.5 or 1.0
    return max(0.0, 1.0 - distance / max_distance)
