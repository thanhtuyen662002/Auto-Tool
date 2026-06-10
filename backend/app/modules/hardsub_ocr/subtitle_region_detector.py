from __future__ import annotations

from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRRegion


class SubtitleRegionDetector:
    def detect_region(
        self,
        video_width: int,
        video_height: int,
        mode: str = "bottom_auto",
        manual_region: dict | None = None,
    ) -> OCRRegion:
        width = max(1, int(video_width))
        height = max(1, int(video_height))
        normalized = (mode or "bottom_auto").strip().lower()

        if normalized == "manual":
            if not manual_region:
                raise ValueError("manual OCR region requires ocr_manual_region.")
            return _clamp_region(
                OCRRegion(
                    x=int(manual_region.get("x", 0)),
                    y=int(manual_region.get("y", 0)),
                    width=int(manual_region.get("width", width)),
                    height=int(manual_region.get("height", height)),
                ),
                width,
                height,
            )

        if normalized == "middle_lower":
            return _clamp_region(
                OCRRegion(x=0, y=int(height * 0.40), width=width, height=int(height * 0.45)),
                width,
                height,
            )

        if normalized == "full_frame":
            return OCRRegion(x=0, y=0, width=width, height=height)

        return _clamp_region(
            OCRRegion(x=0, y=int(height * 0.55), width=width, height=int(height * 0.35)),
            width,
            height,
        )


def _clamp_region(region: OCRRegion, frame_width: int, frame_height: int) -> OCRRegion:
    x = min(max(0, region.x), max(0, frame_width - 1))
    y = min(max(0, region.y), max(0, frame_height - 1))
    width = min(max(1, region.width), frame_width - x)
    height = min(max(1, region.height), frame_height - y)
    return OCRRegion(x=x, y=y, width=width, height=height)
