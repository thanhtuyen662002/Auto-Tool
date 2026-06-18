from __future__ import annotations

import json
from pathlib import Path

from app.modules.visual_style.subtitle_cover_detector import detect_subtitle_cover_from_ocr_debug


def test_detect_subtitle_cover_from_ocr_debug_uses_text_block_position(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 1000, "width": 1080, "height": 700},
                "average_confidence": 0.82,
                "frames": [
                    {
                        "timestamp_ms": 0,
                        "region": {"x": 0, "y": 1000, "width": 1080, "height": 700},
                        "raw_blocks": [
                            {
                                "box": [[120, 410], [960, 410], [960, 482], [120, 482]],
                                "text": "这个真的很好用",
                                "confidence": 0.86,
                            }
                        ],
                    },
                    {
                        "timestamp_ms": 500,
                        "region": {"x": 0, "y": 1000, "width": 1080, "height": 700},
                        "raw_blocks": [
                            {
                                "box": [[132, 418], [948, 418], [948, 488], [132, 488]],
                                "text": "价格也很便宜",
                                "confidence": 0.8,
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    placement = detect_subtitle_cover_from_ocr_debug(
        str(debug_path),
        fallback_height_ratio=0.22,
        fallback_bottom_ratio=0.0,
        padding_ratio=0.03,
    )

    assert placement is not None
    assert placement.block_count == 2
    assert 0.09 <= placement.height_ratio <= 0.16
    assert 0.18 <= placement.bottom_ratio <= 0.24
