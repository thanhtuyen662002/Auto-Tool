from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image

from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRRegion
from app.utils.file_utils import ensure_dir
from app.utils.dependency_manager import ensure_ocr_dependency


class BaseOCRProvider:
    provider_name = "base"

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        raise NotImplementedError


class PaddleOCRProvider(BaseOCRProvider):
    provider_name = "paddleocr"

    def __init__(self, language: str = "ch") -> None:
        report = ensure_ocr_dependency("paddleocr", auto_install=None, warmup_models=False, language=language)
        if not report.available:
            raise RuntimeError(report.message or "Không tìm thấy PaddleOCR. Hãy cài paddleocr hoặc đổi OCR provider.")
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("Không tìm thấy PaddleOCR. Hãy cài paddleocr hoặc đổi OCR provider.") from exc
        self.ocr = PaddleOCR(use_angle_cls=True, lang=language or "ch", show_log=False)

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        crop_path = crop_region(image_path, region)
        warnings: list[str] = []
        try:
            raw = self.ocr.ocr(str(crop_path), cls=True)
            blocks = _parse_paddle_blocks(raw)
            text = " ".join(block["text"] for block in blocks if block.get("text")).strip()
            confidence = _average([float(block.get("confidence", 0.0)) for block in blocks])
        except Exception as exc:
            blocks = []
            text = ""
            confidence = 0.0
            warnings.append(f"OCR frame lỗi: {exc}")
        return OCRFrameResult(
            timestamp_ms=_timestamp_from_frame_name(image_path),
            frame_path=image_path,
            region=region,
            text=text,
            confidence=confidence,
            raw_blocks=blocks,
            warnings=warnings,
        )


class EasyOCRProvider(BaseOCRProvider):
    provider_name = "easyocr"

    def __init__(self, language: str = "ch_sim") -> None:
        report = ensure_ocr_dependency("easyocr", auto_install=None, warmup_models=False, language=language)
        if not report.available:
            raise RuntimeError(report.message or "Không tìm thấy EasyOCR. Hãy cài easyocr hoặc đổi OCR provider.")
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("Không tìm thấy EasyOCR. Hãy cài easyocr hoặc đổi OCR provider.") from exc
        lang = "ch_sim" if language in {"ch", "zh", "zh-cn"} else language
        self.reader = easyocr.Reader([lang], gpu=False)

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        crop_path = crop_region(image_path, region)
        warnings: list[str] = []
        try:
            raw = self.reader.readtext(str(crop_path))
            blocks = [
                {"box": item[0], "text": str(item[1]), "confidence": float(item[2])}
                for item in raw
                if len(item) >= 3
            ]
            text = " ".join(block["text"] for block in blocks if block.get("text")).strip()
            confidence = _average([float(block.get("confidence", 0.0)) for block in blocks])
        except Exception as exc:
            blocks = []
            text = ""
            confidence = 0.0
            warnings.append(f"OCR frame lỗi: {exc}")
        return OCRFrameResult(
            timestamp_ms=_timestamp_from_frame_name(image_path),
            frame_path=image_path,
            region=region,
            text=text,
            confidence=confidence,
            raw_blocks=blocks,
            warnings=warnings,
        )


class MockOCRProvider(BaseOCRProvider):
    provider_name = "mock_ocr"

    def __init__(self, frames: dict[int | str, tuple[str, float] | str] | None = None) -> None:
        self.frames = frames or {}

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        timestamp_ms = _timestamp_from_frame_name(image_path)
        value = self.frames.get(timestamp_ms, self.frames.get(Path(image_path).name, ("", 0.0)))
        if isinstance(value, tuple):
            text, confidence = value
        else:
            text, confidence = str(value), 0.9 if value else 0.0
        return OCRFrameResult(
            timestamp_ms=timestamp_ms,
            frame_path=image_path,
            region=region,
            text=str(text),
            confidence=float(confidence),
            raw_blocks=[{"text": str(text), "confidence": float(confidence)}] if text else [],
        )


def build_ocr_provider(
    provider: str,
    language: str,
    mock_frames: dict[int | str, tuple[str, float] | str] | None = None,
) -> BaseOCRProvider:
    normalized = (provider or "easyocr").strip().lower()
    if normalized == "mock_ocr":
        return MockOCRProvider(mock_frames)
    if normalized == "easyocr":
        return EasyOCRProvider(language=language)
    if normalized == "paddleocr":
        return PaddleOCRProvider(language=language)
    raise ValueError(f"OCR provider chưa được hỗ trợ: {provider}")


def crop_region(image_path: str, region: OCRRegion) -> Path:
    source = Path(image_path)
    crop_dir = ensure_dir(source.parent / "_ocr_crop")
    target = crop_dir / f"{source.stem}_crop.jpg"
    with Image.open(source) as image:
        box = (region.x, region.y, region.x + region.width, region.y + region.height)
        image.crop(box).save(target, quality=92)
    return target


def _timestamp_from_frame_name(image_path: str) -> int:
    match = re.search(r"(\d+)ms", Path(image_path).stem)
    return int(match.group(1)) if match else 0


def _parse_paddle_blocks(raw: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not raw:
        return blocks
    candidates = raw[0] if len(raw) == 1 and isinstance(raw[0], list) else raw
    for item in candidates or []:
        try:
            box = item[0]
            payload = item[1]
            text = str(payload[0])
            confidence = float(payload[1])
            blocks.append({"box": box, "text": text, "confidence": confidence})
        except Exception:
            continue
    return blocks


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
