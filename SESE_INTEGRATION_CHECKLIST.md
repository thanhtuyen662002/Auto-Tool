# Danh sách Tích hợp SESE (SESE Integration Checklist)

Tài liệu này cung cấp danh sách kiểm tra từng bước cụ thể để tích hợp thành công giải pháp **Smart Ending Synchronization Engine (SESE)** vào codebase của dự án Auto Tool Studio.

---

## Bước 1: Cấu hình & Kiểu dữ liệu (Schema & Types)

- [ ] **Sửa đổi Backend Schemas:**
  - File: [project_schema.py](file:///d:/Projects/Auto-Tool/backend/app/schemas/project_schema.py)
  - Hành động:
    - Thêm vào `RenderSettings`:
      ```python
      sese_enabled: bool = True
      sese_mode: str = "auto"
      max_auto_extension_seconds: float = 8.0
      ```
    - Thêm vào `TimelineClip`:
      ```python
      freeze_frame: bool = False
      slow_zoom: bool = False
      ```
- [ ] **Cập nhật Timeline Builder:**
  - File: [timeline_builder.py](file:///d:/Projects/Auto-Tool/backend/app/modules/timeline_builder/timeline_builder.py)
  - Hành động: Thêm `freeze_frame` và `slow_zoom` vào class `TimelineClip` để Pydantic không báo lỗi validation.
- [ ] **Sửa đổi Frontend Types:**
  - File: [project.ts](file:///d:/Projects/Auto-Tool/frontend/src/types/project.ts)
  - Hành động: Bổ sung các trường SESE tương ứng vào interface `RenderSettings` và `TimelineClip`, và bổ sung metadata SESE vào `JobOutput`.
- [ ] **Cấu hình Frontend Defaults:**
  - File: [defaults.ts](file:///d:/Projects/Auto-Tool/frontend/src/config/defaults.ts)
  - Hành động: Thêm các giá trị mặc định cho `sese_enabled: true`, `sese_mode: "auto"`, và `max_auto_extension_seconds: 8.0` vào `DEFAULT_RENDER_SETTINGS`.

---

## Bước 2: Thiết kế & Xây dựng SESE Core Engine

- [ ] **Tạo mới Module SESE Engine:**
  - File: [sese_engine.py](file:///d:/Projects/Auto-Tool/backend/app/modules/sese/sese_engine.py)
  - Hành động:
    - Định nghĩa lớp `SESEEngine`.
    - Viết phương thức `synchronize(timeline: Timeline, voice_duration: float, config: ProjectConfig) -> Timeline`.
    - Triển khai logic so sánh và 3 Case thời lượng:
      - **Case 1 (Voice > Video):**
        - Nếu vượt `max_auto_extension_seconds`: Giữ nguyên timeline, đánh dấu trim voice.
        - Khác: Thử kéo dài clip cuối (`Extend Last Clip`) nếu source video còn dư frame.
        - Nếu không đủ: Tạo thêm clip tĩnh (`Freeze Frame`) chèn vào cuối timeline. Nếu `enable_end_zoom` bật, gán thêm nhãn `slow_zoom = True`.
      - **Case 2 (Video > Voice):** Giữ nguyên timeline, đánh dấu chiến lược `ambient_ending`.
      - **Case 3 (Lệch < 0.5s):** Giữ nguyên timeline.

---

## Bước 3: Nâng cấp Bộ Kết xuất (Renderer Modifications)

- [ ] **Sửa đổi logic Render Clip:**
  - File: [renderer.py](file:///d:/Projects/Auto-Tool/backend/app/modules/renderer/renderer.py)
  - Hành động: Trong hàm `_render_clip`, kiểm tra nếu `clip.freeze_frame` là `True`:
    1. Gọi FFmpeg trích xuất 1 frame PNG tại thời điểm `clip.start` từ `clip.source_path` và ghi ra tệp tạm.
    2. Nếu `clip.slow_zoom` là `True`: Chạy FFmpeg loop kết xuất ảnh PNG tạm đó thành video với filter `zoompan` chuyển động chậm (zoom từ 100% đến 105% qua `total_frames` tính từ `clip.duration * fps`).
    3. Nếu `clip.slow_zoom` là `False`: Chạy FFmpeg loop kết xuất ảnh PNG tạm thành video tĩnh đơn giản với độ phân giải và fps mục tiêu.
    4. Xóa tệp PNG tạm sau khi hoàn tất.
    5. Đảm bảo có khối xử lý lỗi `try...except`. Nếu trích xuất hoặc loop bị lỗi, kết xuất ra 1 clip nền đen (solid black) làm fallback để tiến trình kết xuất không bị gián đoạn.

---

## Bước 4: Tích hợp Pipeline & Các biện pháp bảo vệ (Safeguards)

- [ ] **Bypass SESE khi chạy Preview:**
  - File: [render_worker.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/render_worker.py)
  - Hành động: Trong hàm `_preview_config`, đặt `sese_enabled = False` để vô hiệu hóa SESE, giữ cho preview chạy nhanh dưới 8 giây.
- [ ] **Thay đổi luồng kết xuất trong Pipeline:**
  - File: [output_pipeline.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/output_pipeline.py)
  - Hành động: Trong hàm `render_one_output`:
    1. Chuyển bước sinh kịch bản (`generate_script`) lên trước.
    2. Gọi `voice_generator.generate_voiceover`. Nếu SESE bật trong config, truyền tham số `target_duration = 0.0` (để voice không bị trim cụt).
    3. Chạy chuẩn hóa và đo thời lượng giọng thực tế: `voice_duration`.
    4. Chạy `SESEEngine.synchronize` để nhận timeline mới: `adjusted_timeline`.
    5. Lưu các thông số SESE (`sese_applied`, `added_duration`, `sese_strategy`) vào log chạy và report để QA/Review đọc.
    6. Gọi `renderer.render_timeline` truyền vào `adjusted_timeline`.
    7. Gọi `subtitle_generator.generate_srt` truyền vào `adjusted_timeline.duration` (thời lượng đã cân bằng) thay vì `config.render.duration`.
- [ ] **Điều chỉnh tham số expected_duration của QA Checker:**
  - File: [output_pipeline.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/output_pipeline.py)
  - Hành động: Khi gọi hàm `check_output_video` ở bước QA, truyền tham số `adjusted_timeline.duration` thay thế cho `config.render.duration` để tránh QA Checker đánh FAIL lỗi lệch thời lượng.

---

## Bước 5: Cập nhật Downstream Services (Scoring & Review)

- [ ] **Bảo vệ điểm chất lượng khi dùng SESE:**
  - File: [review_service.py](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py)
  - Hành động:
    - Trong hàm `_technical_score` và `_audio_score`, đọc thông tin `sese_applied` và `added_duration` từ log kết quả của output.
    - Nếu `sese_applied` là `True`, sử dụng mốc so sánh là `config.render.duration + added_duration` thay thế cho `config.render.duration` tĩnh để tránh trừ điểm chất lượng oan của video đã được SESE cân bằng chính xác.

---

## Bước 6: Kiểm thử & Xác nhận (Testing & Verification)

- [ ] **Viết Unit Tests cho SESE Engine:**
  - File: [test_sese.py](file:///d:/Projects/Auto-Tool/backend/tests/test_sese.py)
  - Hành động: Kiểm thử lớp `SESEEngine` với các bộ dữ liệu giả lập cho tất cả 3 Case lệch thời lượng và Max Guard.
- [ ] **Chạy smoke test kiểm chứng:**
  - Hành động: Chạy lại kịch bản AULA F99 thực tế, xác nhận:
    1. Video render thành công mà không có lỗi.
    2. QA checker chấm PASS.
    3. Điểm review chất lượng đạt mức GOOD (>0.85) và không bị trừ điểm oan.
    4. Câu thoại cuối cùng của video nghe trọn vẹn và phụ đề khớp hoàn toàn.
