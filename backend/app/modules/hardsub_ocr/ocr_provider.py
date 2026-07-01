from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from PIL import Image

from app.modules.hardsub_ocr.hardsub_ocr_schema import OCRFrameResult, OCRRegion
from app.utils.file_utils import ensure_dir
from app.utils.dependency_manager import ensure_ocr_dependency
from app.utils.gpu_detector import detect_gpu_status


class BaseOCRProvider:
    provider_name = "base"

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        raise NotImplementedError

    def recognize_batch(self, image_paths: list[str], region: OCRRegion) -> list[OCRFrameResult]:
        return [self.recognize(image_path, region) for image_path in image_paths]


class PaddleOCRProvider(BaseOCRProvider):
    provider_name = "paddleocr"
    _cache_lock = threading.Lock()
    _ocr_cache: dict[str, tuple[Any, threading.Lock]] = {}

    def __init__(self, language: str = "ch") -> None:
        report = ensure_ocr_dependency("paddleocr", auto_install=None, warmup_models=False, language=language)
        if not report.available:
            raise RuntimeError(report.message or "Không tìm thấy PaddleOCR. Hãy cài paddleocr hoặc đổi OCR provider.")

        gpu_status = detect_gpu_status()
        use_gpu = bool(gpu_status.hardware_available)
        cache_key = f"{language}:{'gpu' if use_gpu else 'cpu'}"

        with self._cache_lock:
            cached = self._ocr_cache.get(cache_key)
            if cached is None:
                try:
                    from paddleocr import PaddleOCR
                except ImportError as exc:
                    raise RuntimeError("Không tìm thấy PaddleOCR. Hãy cài paddleocr hoặc đổi OCR provider.") from exc
                
                # Tắt kiểm tra kết nối online đến host model Trung Quốc để tránh bị đơ/treo lúc khởi động
                import os
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

                # Tự động phát hiện card đồ họa rời NVIDIA CUDA
                # Khởi tạo tương thích với cả PaddleOCR cũ (v2.x) và mới (v3.x / paddlex)
                device_str = "gpu" if use_gpu else "cpu"
                ocr_inst = None
                try:
                    ocr_inst = PaddleOCR(
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=True,
                        lang=language or "ch",
                        device=device_str,
                        enable_mkldnn=False  # Tránh lỗi oneDNN instruction crash trên Windows
                    )
                except Exception:
                    try:
                        ocr_inst = PaddleOCR(
                            use_angle_cls=True,
                            lang=language or "ch",
                            show_log=False,
                            use_gpu=use_gpu
                        )
                    except Exception:
                        if use_gpu:
                            try:
                                ocr_inst = PaddleOCR(
                                    use_angle_cls=True,
                                    lang=language or "ch",
                                    show_log=False,
                                    use_gpu=False
                                )
                            except Exception:
                                ocr_inst = None
                        try:
                            if ocr_inst is None:
                                ocr_inst = PaddleOCR(lang=language or "ch")
                        except Exception as final_exc:
                            raise RuntimeError(f"Không thể khởi tạo PaddleOCR: {final_exc}") from final_exc
                cached = (ocr_inst, threading.Lock())
                self._ocr_cache[cache_key] = cached

        self.ocr, self._ocr_lock = cached

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        crop_path = crop_region(image_path, region)
        warnings: list[str] = []
        try:
            with self._ocr_lock:
                try:
                    raw = self.ocr.ocr(str(crop_path), cls=True)
                except Exception:
                    try:
                        if hasattr(self.ocr, "predict"):
                            raw = self.ocr.predict(str(crop_path))
                        else:
                            raw = self.ocr.ocr(str(crop_path))
                    except Exception as inner_exc:
                        raise inner_exc

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

    def recognize_batch(self, image_paths: list[str], region: OCRRegion) -> list[OCRFrameResult]:
        if not image_paths:
            return []
        
        crop_paths = [crop_region(image_path, region) for image_path in image_paths]
        warnings: list[str] = []
        try:
            with self._ocr_lock:
                if hasattr(self.ocr, "predict"):
                    raw_batch = self.ocr.predict([str(p) for p in crop_paths])
                else:
                    try:
                        raw_batch = [self.ocr.ocr(str(p), cls=True) for p in crop_paths]
                    except Exception:
                        raw_batch = [self.ocr.ocr(str(p)) for p in crop_paths]
        except Exception as exc:
            # Fallback chạy tuần tự nếu batch lỗi
            return [self.recognize(image_path, region) for image_path in image_paths]

        results: list[OCRFrameResult] = []
        for image_path, raw in zip(image_paths, raw_batch):
            try:
                blocks = _parse_paddle_blocks(raw)
                text = " ".join(block["text"] for block in blocks if block.get("text")).strip()
                confidence = _average([float(block.get("confidence", 0.0)) for block in blocks])
            except Exception as exc:
                blocks = []
                text = ""
                confidence = 0.0
                warnings.append(f"OCR frame lỗi: {exc}")
            
            results.append(
                OCRFrameResult(
                    timestamp_ms=_timestamp_from_frame_name(image_path),
                    frame_path=image_path,
                    region=region,
                    text=text,
                    confidence=confidence,
                    raw_blocks=blocks,
                    warnings=list(warnings),
                )
            )
        return results



class EasyOCRProvider(BaseOCRProvider):
    provider_name = "easyocr"
    _cache_lock = threading.Lock()
    _reader_cache: dict[str, tuple[Any, threading.Lock]] = {}

    def __init__(self, language: str = "ch_sim") -> None:
        report = ensure_ocr_dependency("easyocr", auto_install=None, warmup_models=False, language=language)
        if not report.available:
            raise RuntimeError(report.message or "Không tìm thấy EasyOCR. Hãy cài easyocr hoặc đổi OCR provider.")
        try:
            import easyocr
        except ImportError as exc:
            raise RuntimeError("Không tìm thấy EasyOCR. Hãy cài easyocr hoặc đổi OCR provider.") from exc
        lang = "ch_sim" if language in {"ch", "zh", "zh-cn"} else language
        
        # Tự động phát hiện card đồ họa rời NVIDIA CUDA
        gpu_status = detect_gpu_status()
        use_gpu = bool(gpu_status.torch_cuda_available)
        cache_key = f"{lang}:{'gpu' if use_gpu else 'cpu'}"

        with self._cache_lock:
            cached = self._reader_cache.get(cache_key)
            if cached is None:
                try:
                    reader = easyocr.Reader([lang], gpu=use_gpu)
                except Exception:
                    if not use_gpu:
                        raise
                    reader = easyocr.Reader([lang], gpu=False)
                cached = (reader, threading.Lock())
                self._reader_cache[cache_key] = cached
        self.reader, self._reader_lock = cached

    def recognize(self, image_path: str, region: OCRRegion) -> OCRFrameResult:
        crop_path = crop_region(image_path, region)
        warnings: list[str] = []
        try:
            with self._reader_lock:
                raw = self.reader.readtext(str(crop_path))
            blocks, text, confidence = _parse_easyocr_blocks(raw)
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

    def recognize_batch(self, image_paths: list[str], region: OCRRegion) -> list[OCRFrameResult]:
        if not image_paths:
            return []
        crop_paths = [crop_region(image_path, region) for image_path in image_paths]
        try:
            with self._reader_lock:
                raw_batch = self.reader.readtext_batched(
                    [str(path) for path in crop_paths],
                    batch_size=min(4, len(crop_paths)),
                    decoder="greedy",
                )
        except Exception:
            return [self.recognize(image_path, region) for image_path in image_paths]

        results: list[OCRFrameResult] = []
        for image_path, raw in zip(image_paths, raw_batch):
            blocks, text, confidence = _parse_easyocr_blocks(raw)
            results.append(
                OCRFrameResult(
                    timestamp_ms=_timestamp_from_frame_name(image_path),
                    frame_path=image_path,
                    region=region,
                    text=text,
                    confidence=confidence,
                    raw_blocks=blocks,
                )
            )
        return results


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

    # Tương thích với PaddleOCR phiên bản mới (v3.x / paddlex) trả về list của OCRResult hoặc chính OCRResult
    first_item = raw[0] if isinstance(raw, list) and len(raw) > 0 else raw
    if first_item is not None and (hasattr(first_item, "rec_texts") or (isinstance(first_item, dict) and "rec_texts" in first_item)):
        rec_polys = first_item.get("rec_polys", [])
        rec_texts = first_item.get("rec_texts", [])
        rec_scores = first_item.get("rec_scores", [])
        for box, text, score in zip(rec_polys, rec_texts, rec_scores):
            if isinstance(text, tuple):
                text = text[0]
            blocks.append({
                "box": _normalize_box(box),
                "text": str(text),
                "confidence": float(score)
            })
        return blocks

    # Tương thích với PaddleOCR phiên bản cũ (v2.x)
    candidates = raw[0] if len(raw) == 1 and isinstance(raw[0], list) else raw
    for item in candidates or []:
        try:
            box = item[0]
            payload = item[1]
            text = str(payload[0])
            confidence = float(payload[1])
            blocks.append({"box": _normalize_box(box), "text": text, "confidence": confidence})
        except Exception:
            continue
    return blocks


def _parse_easyocr_blocks(raw: Any) -> tuple[list[dict[str, Any]], str, float]:
    blocks = [
        {"box": _normalize_box(item[0]), "text": str(item[1]), "confidence": float(item[2])}
        for item in (raw or [])
        if len(item) >= 3
    ]
    text = " ".join(block["text"] for block in blocks if block.get("text")).strip()
    confidence = _average([float(block.get("confidence", 0.0)) for block in blocks])
    return blocks, text, confidence


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _normalize_box(box: Any) -> list[list[float]]:
    points: list[list[float]] = []
    if box is None:
        return points
    for point in box:
        try:
            points.append([float(point[0]), float(point[1])])
        except Exception:
            continue
    return points
