from __future__ import annotations

import logging
from pathlib import Path
from app.adapters.gemini_adapter import GeminiAdapter, ScriptGenerationError

logger = logging.getLogger(__name__)

def detect_subtitle_via_ai(
    image_paths: list[str],
    api_keys: list[str],
    model_name: str = "gemini-3.1-flash-lite",
) -> dict | None:
    """
    Sử dụng Gemini Vision để phân tích các frame ảnh từ video Douyin nguồn
    nhằm phát hiện sự xuất hiện của phụ đề tiếng Trung (hardsub) và lấy tọa độ Y của chúng.

    Tham số:
        image_paths: Danh sách các đường dẫn ảnh frame (3-4 ảnh cách đều).
        api_keys: Danh sách các API Key của Gemini để xoay vòng.
        model_name: Tên model Gemini có hỗ trợ hình ảnh (Vision).

    Trả về:
        Một dict chứa kết quả phân tích hoặc None nếu có lỗi/thất bại:
        {
            "has_chinese_subtitles": bool,
            "y_min_percent": float,
            "y_max_percent": float,
            "confidence": float,
            "reason": str
        }
    """
    if not api_keys:
        logger.warning("ai_subtitle_detector: Không có Gemini API Key để gọi AI Vision.")
        return None

    # Lọc các file ảnh thực tế tồn tại
    valid_paths = [p for p in image_paths if Path(p).exists() and Path(p).is_file()]
    if not valid_paths:
        logger.warning("ai_subtitle_detector: Không tìm thấy ảnh frame hợp lệ nào để gửi cho Gemini.")
        return None

    # Chỉ gửi tối đa 4 ảnh để tránh quá tải token và tốc độ phản hồi nhanh hơn
    selected_paths = valid_paths[:4]

    prompt = (
        "Bạn là một chuyên gia về xử lý video và thị giác máy tính.\n"
        "Hãy phân tích kỹ các bức ảnh được gửi kèm (đây là các frame ảnh được trích xuất từ một video ngắn Douyin/TikTok).\n"
        "Nhiệm vụ của bạn là kiểm tra xem video nguồn này có phụ đề tiếng Trung dính chết vào video hay không (hardsub - chữ tiếng Trung Quốc chạy ở phía dưới hoặc đôi khi ở giữa màn hình để hiển thị giọng thoại).\n\n"
        "Hãy tuân thủ các quy tắc sau:\n"
        "1. Nếu video gốc KHÔNG có phụ đề tiếng Trung dính kèm (ví dụ: video sạch hoàn toàn, hoặc chỉ hiển thị văn bản quảng cáo tĩnh, logo thương hiệu, giỏ hàng, nhãn dán sản phẩm mà không phải phụ đề thoại chạy theo giọng nói), hãy xác định has_chinese_subtitles = false.\n"
        "2. Nếu video có phụ đề tiếng Trung dính kèm:\n"
        "   - Xác định vùng dải phụ đề tiếng Trung này dọc theo chiều dọc màn hình (trục Y).\n"
        "   - Đo lường và trả về tọa độ y_min_percent và y_max_percent dưới dạng tỷ lệ phần trăm từ đỉnh video xuống đáy video (từ 0 đến 100, trong đó 0% là đỉnh trên cùng, 100% là đáy dưới cùng của video).\n"
        "   - Ví dụ: Nếu phụ đề tiếng Trung nằm ở dải sát đáy từ khoảng 80% đến 92% chiều cao video, hãy trả về y_min_percent = 80 và y_max_percent = 92.\n"
        "   - Ví dụ: Nếu phụ đề tiếng Trung nằm cao hơn, từ 72% đến 84% chiều cao video, hãy trả về y_min_percent = 72 và y_max_percent = 84.\n"
        "3. Hãy bỏ qua các logo, giỏ hàng, sticker hay văn bản quảng cáo tĩnh khi tính toán toạ độ này, chỉ tập trung vào dải phụ đề thoại chính.\n\n"
        "Mẫu JSON kết quả bắt buộc phải trả về đúng định dạng sau:\n"
        "{\n"
        "  \"has_chinese_subtitles\": true,\n"
        "  \"y_min_percent\": 80.0,\n"
        "  \"y_max_percent\": 92.0,\n"
        "  \"confidence\": 0.95,\n"
        "  \"reason\": \"Giải thích ngắn gọn tại sao bạn chọn tọa độ này (ví dụ: Phụ đề tiếng Trung màu trắng chạy xuyên suốt sát đáy video từ 80% đến 92%)\"\n"
        "}"
    )

    try:
        logger.info("ai_subtitle_detector: Đang gọi Gemini Vision để định vị phụ đề Trung Quốc qua %d ảnh frame...", len(selected_paths))
        # Sử dụng GeminiAdapter có sẵn trong dự án
        adapter = GeminiAdapter(
            api_key=None,
            model_name=model_name,
            api_keys=api_keys,
            timeout_seconds=35.0
        )
        
        payload = adapter.generate_json_with_images(prompt, selected_paths)
        
        has_sub = bool(payload.get("has_chinese_subtitles"))
        confidence = float(payload.get("confidence") or 0.0)
        
        # Validate kiểu dữ liệu của tọa độ
        y_min = payload.get("y_min_percent")
        y_max = payload.get("y_max_percent")
        
        if has_sub and (y_min is None or y_max is None):
            logger.warning("ai_subtitle_detector: Gemini báo có phụ đề nhưng thiếu tọa độ y_min/y_max. Bỏ qua kết quả.")
            return None

        result = {
            "has_chinese_subtitles": has_sub,
            "y_min_percent": float(y_min) if y_min is not None else 0.0,
            "y_max_percent": float(y_max) if y_max is not None else 0.0,
            "confidence": confidence,
            "reason": str(payload.get("reason") or "Không có lý do chi tiết.")
        }
        
        logger.info(
            "ai_subtitle_detector: Kết quả AI Vision: has_sub=%s, y_min=%.1f%%, y_max=%.1f%%, confidence=%.2f. Lý do: %s",
            result["has_chinese_subtitles"], result["y_min_percent"], result["y_max_percent"],
            result["confidence"], result["reason"]
        )
        return result

    except ScriptGenerationError as exc:
        logger.error("ai_subtitle_detector: Lỗi gọi Gemini API: %s", exc)
        return None
    except Exception as exc:
        logger.exception("ai_subtitle_detector: Lỗi không xác định khi phân tích phụ đề bằng AI: %s", exc)
        return None
