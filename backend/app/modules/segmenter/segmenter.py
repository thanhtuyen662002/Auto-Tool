from __future__ import annotations

import hashlib
import random

from app.schemas.media_schema import MediaFile, VideoSegment


class Segmenter:
    def create_segments(self, media_files: list[MediaFile], cut_intensity: int) -> list[VideoSegment]:
        min_duration, max_duration = self._duration_range(cut_intensity)
        segments: list[VideoSegment] = []

        for media in media_files:
            usable_start = 0.3
            usable_end = max(0.0, media.duration - 0.3)
            cursor = usable_start

            while cursor + min_duration <= usable_end:
                raw_duration = random.uniform(min_duration, max_duration)
                end = min(cursor + raw_duration, usable_end)
                duration = end - cursor

                if duration < min_duration:
                    break

                segments.append(
                    VideoSegment(
                        id=self._segment_id(media.path, cursor, end),
                        source_path=media.path,
                        start=round(cursor, 3),
                        end=round(end, 3),
                        duration=round(duration, 3),
                        score=round(random.uniform(0.5, 1.0), 3),
                    )
                )
                cursor = end

        return segments

    @staticmethod
    def _segment_id(source_path: str, start: float, end: float) -> str:
        raw_value = f"{source_path}|{start:.3f}|{end:.3f}".encode("utf-8")
        return hashlib.sha1(raw_value).hexdigest()[:12]

    @staticmethod
    def _duration_range(cut_intensity: int) -> tuple[float, float]:
        cut_intensity = max(0, min(100, cut_intensity))
        if cut_intensity <= 30:
            return 2.5, 3.5
        if cut_intensity <= 70:
            return 1.7, 2.8
        return 1.2, 2.2
