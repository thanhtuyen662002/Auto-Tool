from __future__ import annotations

import itertools
from pathlib import Path

from app.adapters.ffmpeg_adapter import probe_video
from app.modules.douyin_reup.subtitle_timing_guard import parse_srt_blocks
from app.modules.silent_immersive_reup.silent_schema import ImmersiveCaptionLine, SilentVisualSegment, VisualSegmentType


class ImmersiveCaptionGenerator:
    def generate_captions(
        self,
        video_path: str,
        segments: list[SilentVisualSegment],
        strategy: str,
        product_context: dict | None = None,
        ocr_translated_srt_path: str | None = None,
    ) -> list[ImmersiveCaptionLine]:
        if ocr_translated_srt_path and Path(ocr_translated_srt_path).exists():
            captions = self._captions_from_ocr(ocr_translated_srt_path, video_path)
            if captions:
                return captions

        if not segments:
            media = probe_video(video_path)
            segments = [
                SilentVisualSegment(
                    id="seg_001",
                    video_path=video_path,
                    start=0,
                    end=media.duration,
                    duration=media.duration,
                    segment_type=VisualSegmentType.product_reveal,
                    visual_score=0.5,
                )
            ]

        templates = _templates(strategy, product_context)
        captions: list[ImmersiveCaptionLine] = []
        for index, (segment, text) in enumerate(zip(segments, itertools.cycle(templates)), start=1):
            if segment.duration < 0.35:
                continue
            captions.append(
                ImmersiveCaptionLine(
                    index=index,
                    start=segment.start,
                    end=segment.end,
                    text=_short_caption(_scene_specific_text(segment.segment_type, text, product_context)),
                    source="visual_generated",
                    segment_id=segment.id,
                )
            )
        return captions

    @staticmethod
    def _captions_from_ocr(path: str, video_path: str) -> list[ImmersiveCaptionLine]:
        captions: list[ImmersiveCaptionLine] = []
        try:
            blocks = parse_srt_blocks(path)
        except Exception:
            return []
        for index, block in enumerate(blocks, start=1):
            captions.append(
                ImmersiveCaptionLine(
                    index=index,
                    start=block.start,
                    end=block.end,
                    text=_short_caption(block.text),
                    source="ocr_translation",
                )
            )
        return captions


def _templates(strategy: str, product_context: dict | None) -> list[str]:
    name = _product_name(product_context)
    cta = _cta(product_context)
    feature = _first_feature(product_context)
    if strategy == "product_review_voiceover":
        return [
            f"{name} hợp với nhu cầu dùng hằng ngày" if name else "Món này hợp với nhu cầu dùng hằng ngày",
            f"Thiết kế gọn, thao tác nhìn khá đơn giản",
            f"Điểm đáng chú ý là {feature}" if feature else "Nhìn tổng thể khá gọn và dễ dùng",
            cta or "Có thể tham khảo thêm nếu thấy phù hợp",
        ]
    if strategy == "sales_recut":
        return [
            f"{name} nhìn nhỏ mà khá tiện" if name else "Món đồ nhỏ mà nhìn khá tiện",
            f"Góc nhà gọn hơn khi dùng đúng chỗ",
            "Thao tác đơn giản, dễ quan sát",
            cta or "Lưu lại để tham khảo nhé",
        ]
    return [
        f"{name} nhìn khá gọn gàng" if name else "Món đồ này nhìn khá gọn gàng",
        "Thiết kế đặt trong nhà khá hợp",
        f"Phù hợp khi cần {feature}" if feature else "Dùng trong nhà tiện hơn hẳn",
        "Nhỏ vậy mà khá hữu ích",
        cta or "Ai thích đồ gọn gàng nên lưu lại",
    ]


def _scene_specific_text(segment_type: VisualSegmentType, fallback: str, product_context: dict | None) -> str:
    name = _product_name(product_context)
    if segment_type == VisualSegmentType.unboxing:
        return f"Mở hộp {name} nhìn khá chỉn chu" if name else "Mở hộp nhìn khá chỉn chu"
    if segment_type == VisualSegmentType.closeup:
        return f"Cận cảnh chi tiết của {name}" if name else "Cận cảnh chi tiết sản phẩm"
    if segment_type == VisualSegmentType.demo:
        return "Thao tác sử dụng nhìn khá đơn giản"
    if segment_type == VisualSegmentType.before_after:
        return "Nhìn phần trước và sau khá rõ khác biệt"
    if segment_type == VisualSegmentType.result:
        return "Kết quả sau khi dùng nhìn gọn hơn"
    return fallback


def _product_name(product_context: dict | None) -> str:
    if not product_context:
        return ""
    return str(product_context.get("product_name") or product_context.get("name") or "").strip()


def _first_feature(product_context: dict | None) -> str:
    if not product_context:
        return ""
    features = product_context.get("features") or []
    if isinstance(features, str):
        features = [line.strip() for line in features.splitlines() if line.strip()]
    if not isinstance(features, list) or not features:
        return ""
    return str(features[0]).strip()


def _cta(product_context: dict | None) -> str:
    if not product_context:
        return ""
    return str(product_context.get("cta") or "").strip()


def _short_caption(text: str, max_chars: int = 52) -> str:
    cleaned = " ".join(text.replace("\n", " ").split())
    if len(cleaned) <= max_chars:
        return cleaned
    words = cleaned.split()
    result: list[str] = []
    for word in words:
        candidate = " ".join([*result, word])
        if len(candidate) > max_chars:
            break
        result.append(word)
    return " ".join(result) or cleaned[:max_chars].rstrip()
