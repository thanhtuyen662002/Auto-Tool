# Phân tích Tác động Nâng cấp (Upgrade Impact Analysis)

Tài liệu này đánh giá độ khó, giải pháp kỹ thuật đề xuất, rủi ro và tác động đối với codebase khi thực hiện nâng cấp các tính năng bị thiếu hụt trong workflow Affiliate của Auto Tool Studio.

---

## 1. Hỗ trợ Ảnh tĩnh làm Clip nguồn trong Timeline

*   **Mức độ khó:** **DỄ (EASY)**
*   **Giải pháp Kỹ thuật:**
    1.  **Backend Scanner:** Cập nhật `MediaScanner` để quét thêm các đuôi file ảnh `.png`, `.jpg`, `.jpeg`, `.webp` bên cạnh video.
    2.  **Timeline Builder:** Gán thời lượng mặc định (ví dụ: 2-3 giây) cho các tệp ảnh khi đưa vào làm clip trên timeline.
    3.  **Renderer:** Cập nhật hàm `_render_clip` của `Renderer` để phát hiện tệp tin đầu vào là ảnh tĩnh. Sử dụng bộ lọc FFmpeg `-loop 1 -i image_path -t duration` để chuyển đổi ảnh tĩnh thành một clip video 9:16 tạm thời trước khi chạy lệnh `concat` ghép nối.
*   **Tác động Codebase:** Rất thấp, chỉ chỉnh sửa cục bộ tại `media_scanner.py` và `renderer.py`.
*   **Rủi ro:** Cần đảm bảo độ phân giải ảnh tĩnh được scale đúng tỷ lệ đích (ví dụ: 1080x1920) để tránh lỗi lệch khung hình khi ghép với video clip khác.

---

## 2. Tính năng Nhân bản Dự án nhanh (Duplicate Project)

*   **Mức độ khó:** **DỄ (EASY)**
*   **Giải pháp Kỹ thuật:**
    1.  **API Endpoint:** Thêm endpoint `POST /api/projects/{project_id}/duplicate` trong `api.py`. Endpoint này đọc cấu hình từ SQLite, nhân bản dữ liệu, tạo UUID mới và lưu lại một dòng dự án mới với tên hậu tố `- Copy`.
    2.  **Frontend UI:** Thêm một nút bấm hành động "Duplicate" trên trang danh sách dự án (`ResultsPage`) hoặc trang cấu hình dự án (`RenderSettingsPage`).
*   **Tác động Codebase:** Rất thấp, chỉ bổ sung endpoint và một nút bấm UI đơn giản.
*   **Rủi ro:** Không có rủi ro kỹ thuật.

---

## 3. Thuyết minh đối thoại đa giọng đọc (Multi-speaker TTS)

*   **Mức độ khó:** **TRUNG BÌNH (MEDIUM)**
*   **Giải pháp Kỹ thuật:**
    1.  **Schema kịch bản:** Bổ sung trường `voice_id` hoặc `gender_hint` (nam/nữ) vào từng dòng thoại thuyết minh trong cấu trúc schema `SubtitleLine` và kịch bản `ProductVideoScript`.
    2.  **AI Prompts:** Cập nhật prompt gửi đến Gemini để sinh kịch bản phân vai rõ ràng (ví dụ: Nhân vật A nói câu 1, Nhân vật B nói câu 2).
    3.  **Voice Generator:** Chỉnh sửa hàm `_generate_consistent_voice_segments` trong `voice_generator.py` để loại bỏ cơ chế khóa cứng một nhà cung cấp (`lock_provider`). Thay vào đó, gọi TTS riêng biệt cho từng dòng thoại dựa trên cấu hình giọng đọc của nhân vật tương ứng trước khi ghép nối thành file audio tổng.
*   **Tác động Codebase:** Trung bình. Cần thay đổi nhẹ về schema lưu trữ kịch bản và logic ghép nối âm thanh.
*   **Rủi ro:** Thời gian sinh giọng đọc thuyết minh có thể tăng lên do phải thực hiện nhiều API calls TTS độc lập cho từng dòng thoại thay vì gộp chung.

---

## 4. Trình dựng Timeline kéo thả trực quan (Visual Timeline Editor)

*   **Mức độ khó:** **KHÓ (HARD)**
*   **Giải pháp Kỹ thuật:**
    1.  **Frontend UI:** Xây dựng một giao diện chỉnh sửa trực quan (Visual Drag-and-Drop) sử dụng thư viện `@dnd-kit/core` hoặc `react-beautiful-dnd` hiển thị các phân cảnh nằm trên timeline.
    2.  **API Data Flow:** Hiện tại timeline được sinh tự động ngay trước lúc render ở backend và không được lưu trữ vào DB. Để hỗ trợ chỉnh sửa, cần tạo API `POST /api/projects/{project_id}/timeline` để lưu trạng thái dòng thời gian do người dùng cấu hình vào SQLite DB.
    3.  **Render Worker:** Sửa đổi `render_worker.py` để ưu tiên đọc dòng thời gian đã biên tập và lưu trữ trong SQLite thay vì tự động chạy thuật toán sinh timeline mới.
*   **Tác động Codebase:** Rất cao. Phá vỡ triết lý "thiết lập nhanh - sinh tự động" hiện tại, yêu cầu lưu trữ trạng thái timeline phức tạp và thay đổi cơ chế sinh timeline ở backend.
*   **Rủi ro:** Rất dễ phát sinh lỗi đồng bộ dữ liệu giữa video nguồn và timeline nếu người dùng xóa bớt tệp tin video thô trên máy tính sau khi đã sắp xếp timeline.
