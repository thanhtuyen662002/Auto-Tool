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
    assert 0.05 <= placement.height_ratio <= 0.12
    assert 0.18 <= placement.bottom_ratio <= 0.24
    assert len(placement.segments) == 2
    assert placement.segments[0].start == 0
    assert placement.segments[0].end == 0.25


def test_detect_subtitle_cover_from_full_frame_mid_screen_subtitle(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug_mid_screen.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                "average_confidence": 0.78,
                "frames": [
                    {
                        "timestamp_ms": 0,
                        "region": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                        "raw_blocks": [
                            {
                                "box": [[170, 720], [910, 720], [910, 790], [170, 790]],
                                "text": "\u8fd9\u4e2a\u6536\u7eb3\u771f\u7684\u5f88\u65b9\u4fbf",
                                "confidence": 0.78,
                            }
                        ],
                    },
                    {
                        "timestamp_ms": 1000,
                        "region": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                        "raw_blocks": [
                            {
                                "box": [[160, 735], [920, 735], [920, 805], [160, 805]],
                                "text": "\u653e\u5728\u5ba2\u5385\u4e5f\u4e0d\u5360\u5730\u65b9",
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
        fallback_height_ratio=0.12,
        fallback_bottom_ratio=0.0,
        padding_ratio=0.03,
    )

    assert placement is not None
    assert placement.source == "ocr_debug_timed_blocks"
    assert placement.bottom_ratio > 0.5
    assert len(placement.segments) == 2
    assert all(0.34 <= segment.top_ratio <= 0.42 for segment in placement.segments)
    assert all(0.40 <= segment.bottom_edge_ratio <= 0.46 for segment in placement.segments)


def test_detect_subtitle_cover_from_ocr_debug_keeps_per_timestamp_positions(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 900, "width": 1080, "height": 800},
                "frames": [
                    {
                        "timestamp_ms": 0,
                        "region": {"x": 0, "y": 900, "width": 1080, "height": 800},
                        "raw_blocks": [
                            {
                                "box": [[150, 500], [930, 500], [930, 570], [150, 570]],
                                "text": "这个真的很好用",
                                "confidence": 0.9,
                            },
                            {
                                "box": [[60, 40], [260, 40], [260, 90], [60, 90]],
                                "text": "推荐",
                                "confidence": 0.95,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 1000,
                        "region": {"x": 0, "y": 900, "width": 1080, "height": 800},
                        "raw_blocks": [
                            {
                                "box": [[180, 430], [900, 430], [900, 500], [180, 500]],
                                "text": "价格也很便宜",
                                "confidence": 0.88,
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
        padding_ratio=0.02,
    )

    assert placement is not None
    assert placement.source == "ocr_debug_timed_blocks"
    assert len(placement.segments) == 2
    assert placement.segments[0].top_ratio > placement.segments[1].top_ratio
    assert placement.segments[0].bottom_edge_ratio > placement.segments[1].bottom_edge_ratio
    assert 0.05 <= placement.segments[0].bottom_edge_ratio - placement.segments[0].top_ratio <= 0.09


def test_detect_subtitle_cover_ignores_moving_channel_watermark(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug_watermark.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                "average_confidence": 0.7,
                "frames": [
                    {
                        "timestamp_ms": 0,
                        "raw_blocks": [
                            {
                                "box": [[160, 1320], [920, 1320], [920, 1390], [160, 1390]],
                                "text": "这个收纳真的很方便",
                                "confidence": 0.72,
                            },
                            {
                                "box": [[760, 1760], [1040, 1760], [1040, 1815], [760, 1815]],
                                "text": "小店好物推荐",
                                "confidence": 0.94,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 1000,
                        "raw_blocks": [
                            {
                                "box": [[150, 1326], [930, 1326], [930, 1395], [150, 1395]],
                                "text": "放在厨房也不占地方",
                                "confidence": 0.75,
                            },
                            {
                                "box": [[20, 1680], [250, 1680], [250, 1738], [20, 1738]],
                                "text": "关注我",
                                "confidence": 0.96,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 2000,
                        "raw_blocks": [
                            {
                                "box": [[155, 1322], [925, 1322], [925, 1392], [155, 1392]],
                                "text": "这款可以折叠起来",
                                "confidence": 0.73,
                            },
                            {
                                "box": [[830, 1600], [1060, 1600], [1060, 1656], [830, 1656]],
                                "text": "直播间同款",
                                "confidence": 0.92,
                            },
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    placement = detect_subtitle_cover_from_ocr_debug(
        str(debug_path),
        fallback_height_ratio=0.12,
        fallback_bottom_ratio=0.0,
        padding_ratio=0.03,
    )

    assert placement is not None
    assert placement.source == "ocr_debug_timed_blocks"
    assert 0.22 <= placement.bottom_ratio <= 0.32
    assert all(segment.bottom_edge_ratio < 0.78 for segment in placement.segments)
    assert placement.block_count == 3


def test_detect_subtitle_cover_uses_bottom_fallback_for_noisy_midframe_ocr(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug_noisy_midframe.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 720,
                "frame_height": 1280,
                "region": {"x": 0, "y": 704, "width": 720, "height": 448},
                "average_confidence": 0.02,
                "frames": [
                    {
                        "timestamp_ms": 9000,
                        "region": {"x": 0, "y": 704, "width": 720, "height": 448},
                        "raw_blocks": [
                            {
                                "box": [[200, 60], [260, 60], [260, 96], [200, 96]],
                                "text": "瓮",
                                "confidence": 0.004,
                            },
                            {
                                "box": [[470, 380], [540, 380], [540, 415], [470, 415]],
                                "text": "哑",
                                "confidence": 0.006,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 10000,
                        "region": {"x": 0, "y": 704, "width": 720, "height": 448},
                        "raw_blocks": [
                            {
                                "box": [[210, 95], [280, 95], [280, 130], [210, 130]],
                                "text": "盥",
                                "confidence": 0.003,
                            },
                            {
                                "box": [[505, 405], [560, 405], [560, 430], [505, 430]],
                                "text": "川",
                                "confidence": 0.004,
                            },
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
        padding_ratio=0.035,
    )

    assert placement is not None
    assert placement.source == "ocr_debug_bottom_fallback"
    assert placement.height_ratio == 0.12
    assert placement.bottom_ratio == 0
    assert placement.segments == ()


def test_detect_subtitle_cover_filters_out_static_text(tmp_path: Path) -> None:
    debug_path = tmp_path / "ocr_debug_static.json"
    debug_path.write_text(
        json.dumps(
            {
                "frame_width": 1080,
                "frame_height": 1920,
                "region": {"x": 0, "y": 0, "width": 1080, "height": 1920},
                "average_confidence": 0.85,
                "frames": [
                    {
                        "timestamp_ms": 0,
                        "raw_blocks": [
                            # Dynamic subtitle block
                            {
                                "box": [[150, 1300], [930, 1300], [930, 1370], [150, 1370]],
                                "text": "今天给大家介绍这款水壶",
                                "confidence": 0.92,
                            },
                            # Static product brand/logo block
                            {
                                "box": [[400, 300], [680, 300], [680, 350], [400, 350]],
                                "text": "超级品牌水壶",
                                "confidence": 0.96,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 1000,
                        "raw_blocks": [
                            # Dynamic subtitle block
                            {
                                "box": [[160, 1305], [920, 1305], [920, 1375], [160, 1375]],
                                "text": "它采用双层不锈钢材质",
                                "confidence": 0.90,
                            },
                            # Static product brand/logo block (same text and position)
                            {
                                "box": [[402, 302], [678, 302], [678, 352], [402, 352]],
                                "text": "超级品牌水壶",
                                "confidence": 0.95,
                            },
                        ],
                    },
                    {
                        "timestamp_ms": 2000,
                        "raw_blocks": [
                            # Dynamic subtitle block
                            {
                                "box": [[180, 1295], [900, 1295], [900, 1365], [180, 1365]],
                                "text": "保温效果超级棒",
                                "confidence": 0.94,
                            },
                            # Static product brand/logo block (same text and position)
                            {
                                "box": [[398, 298], [682, 298], [682, 348], [398, 348]],
                                "text": "超级品牌水壶",
                                "confidence": 0.97,
                            },
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    placement = detect_subtitle_cover_from_ocr_debug(
        str(debug_path),
        fallback_height_ratio=0.12,
        fallback_bottom_ratio=0.0,
        padding_ratio=0.03,
    )

    assert placement is not None
    assert placement.source == "ocr_debug_timed_blocks"
    # It should detect and cover the dynamic subtitle blocks (around y=1300)
    # The bottom_ratio should correspond to the bottom of the subtitle blocks (~1370 / 1920 -> ~0.28 bottom_ratio)
    assert 0.25 <= placement.bottom_ratio <= 0.32
    assert placement.block_count == 3
    # Ensure it did NOT cover the static text block at y=300 (top of the video)
    # The segments should all be around y=1300 (top_ratio ~ 0.64)
    assert all(0.60 <= segment.top_ratio <= 0.70 for segment in placement.segments)
