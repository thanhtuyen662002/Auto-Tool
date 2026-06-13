# Đánh giá Độc lập Kiến trúc & Xác thực SESE (SESE Architecture Validation)

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Kiểm chứng tính bền vững của kiến trúc SESE trước khi tiến hành code B7, đảm bảo không tích tụ technical debt và bảo toàn độ ổn định của render pipeline.

---

## 1. Timeline Builder Dependency Audit

### Câu hỏi & Trả lời:
1. **Timeline Builder có phụ thuộc Script không?**
   - **KHÔNG.** Lớp `ProductTimelineBuilder` chỉ nhận `segments` và `target_duration` để dựng các phân cảnh visual, hoàn toàn không có thông tin hay phụ thuộc vào nội dung kịch bản thoại (script).
2. **Timeline Builder có phụ thuộc Voice Duration không?**
   - **KHÔNG.** Tiến trình dựng timeline visual thô hoạt động độc lập và dựa trên mốc thời gian tĩnh ban đầu.
3. **Timeline Builder có phụ thuộc Subtitle Generator không?**
   - **KHÔNG.** Timeline Builder được thực hiện trước, sau đó mới đến Subtitle Generator.
4. **Có module nào yêu cầu Timeline phải được render trước khi Voice được sinh ra không?**
   - **KHÔNG.** Việc kết xuất visual video (`render_visual`) và sinh âm thanh TTS là hai tác vụ song song, độc lập. Chúng chỉ bắt buộc phải hội tụ ở bước mix cuối cùng (`render_final_video` của `OverlayRenderer`).
5. **Việc đổi thứ tự pipeline thành `Timeline Build` → `Voice Generation` → `SESE` → `Render Visual` có an toàn 100% không?**
   - **CÓ, AN TOÀN 100%.** SESE hoạt động hoàn toàn ở mức cấu trúc dữ liệu (chỉnh sửa list of clips trong bộ nhớ của đối tượng `Timeline` trước khi đẩy sang Renderer), giúp Renderer tạo ra visual video khớp hoàn toàn với file âm thanh.

### Sơ đồ Call Graph mới sau khi đổi thứ tự pipeline:
```txt
render_project() [render_worker.py]
  └── ProductTimelineBuilder.build_timelines() (Dựng timeline tĩnh ban đầu)
  └── render_one_output() [output_pipeline.py]
        ├── ScriptWriter.generate_script()
        ├── VoiceGenerator.generate_voiceover() (Sinh TTS đầy đủ, target_duration = 0.0)
        ├── SESEEngine.synchronize(timeline, voice_duration) (SESE chỉnh sửa clip cuối)
        ├── Renderer.render_timeline(adjusted_timeline) (Render visual video khớp chính xác)
        │     └── SpecialClipRenderer.render_freeze_frame() (Tách biệt xử lý freeze/zoom)
        ├── SubtitleGenerator.generate_srt() / generate_ass()
        └── OverlayRenderer.render_final_video() (Trộn final MP4)
```

---

## 2. Renderer Responsibility Audit

### Phân tích Kiến trúc
Việc chèn thêm logic trích xuất frame PNG và tạo video zoompan của FFmpeg trực tiếp vào `_render_clip` của `renderer.py` sẽ làm phình to tệp cốt lõi này, vi phạm nguyên tắc Đơn nhiệm (Single Responsibility Principle) và tăng độ phức tạp khi viết Unit Test.

### So sánh Phương án Thiết kế:

| Tiêu chí | A. Nhúng trực tiếp trong `renderer.py` | B. Tạo `SpecialClipRenderer` riêng |
| :--- | :--- | :--- |
| **Maintainability** | **7/10** (Tệp phình to, chứa nhiều nhánh FFmpeg khác biệt) | **9/10** (Cô lập tốt, dễ dàng bổ sung các hiệu ứng kết thúc khác) |
| **Testability** | **7/10** (Khó test riêng lẻ lệnh FFmpeg của freeze frame) | **9/10** (Dễ viết mock unit test cho riêng phần kết xuất clip tĩnh) |
| **Coupling** | **6/10** (Gắn kết chặt chẽ Renderer chính với bộ lọc zoompan) | **9/10** (Renderer chính chỉ làm nhiệm vụ điều phối và concat clip) |
| **Risk** | **7/10** (Dễ gây lỗi cho luồng render clip video động cơ bản) | **9.5/10** (An toàn, nếu không phải freeze frame thì chạy tiếp code cũ) |

### Khuyến nghị cuối cùng:
**Chọn Phương án B (Tách biệt SpecialClipRenderer):**
Tạo tệp hỗ trợ `backend/app/modules/renderer/special_clip_renderer.py` để đóng gói toàn bộ logic trích xuất ảnh PNG và chạy lệnh loop/zoompan của FFmpeg. Lớp `Renderer` chính chỉ đóng vai trò điều hướng sang tệp này khi clip có `freeze_frame = True`.

---

## 3. Feature Flag Strategy

### Đánh giá rủi ro khi đặt `sese_enabled = True` mặc định:
- Có nguy cơ phát sinh lỗi không tương thích phiên bản FFmpeg trên môi trường người dùng (ví dụ máy khách thiếu hoặc phiên bản cũ không hỗ trợ đầy đủ filter `zoompan` nâng cao), dẫn đến crash hàng loạt render job.
- Việc kéo dài video có thể không đúng ý đồ sản xuất của một số người dùng đã quen với luồng cắt ngắn cũ.

### So sánh:
- **A. Mặc định bật (Default ON):** Giúp sửa nhanh lỗi cho phần đông người dùng nhưng rủi ro gián đoạn cao.
- **B. Mặc định tắt (Default OFF) + Feature Flag:** An toàn nhất, cho phép người dùng tự opt-in thử nghiệm và báo cáo lỗi trước khi rollout đại trà.

### Chiến lược Rollout an toàn nhất:
1. Đặt `sese_enabled: bool = False` mặc định trong mã nguồn.
2. Cung cấp checkbox điều khiển rõ ràng tại giao diện Render Settings (`frontend`).
3. Khuyến nghị bật tính năng cho người dùng thông qua tooltip/hướng dẫn.
4. Sau 1-2 phiên bản chạy ổn định, chuyển cấu hình mặc định sang `True` (Default ON).

---

## 4. Migration Safety Review

### Tương thích ngược của dữ liệu cũ (Backward Compatibility):
- **Hoàn toàn tương thích.**
- **Bằng chứng kỹ thuật:** Toàn bộ cấu hình dự án được lưu dạng JSON và deserialize qua thư viện Pydantic. Khi ta thêm các trường mới vào `RenderSettings` và `TimelineClip` schema, Pydantic sẽ tự động gán giá trị mặc định đã khai báo sẵn nếu các trường này bị thiếu trong dữ liệu JSON cũ:
  ```python
  sese_enabled: bool = False  # Tự động nhận False đối với dự án cũ
  sese_mode: str = "auto"
  max_auto_extension_seconds: float = 8.0
  ```
  Do đó, không có bất kỳ rủi ro deserialize thất bại (deserialization crash) nào đối với các dự án cũ trong DB.

---

## 5. Kết luận & Phê duyệt (Final Recommendation)

### **Phán quyết: APPROVE WITH CHANGES (PHÊ DUYỆT CÓ ĐIỀU CHỈNH)**

Các thay đổi bắt buộc phải tuân thủ khi viết code triển khai B7:
1. **Cô lập mã nguồn kết xuất:** Tách biệt logic render Freeze Frame/Slow Zoom ra một tệp riêng `special_clip_renderer.py` đặt trong module `renderer` để bảo tồn sự sạch sẽ của core renderer.
2. **Cưỡng bức tắt SESE khi Preview:** Force `sese_enabled = False` trong preview mode (`_preview_config` trong `render_worker.py`).
3. **Đồng bộ hóa mốc thời gian QA/Review:** Cập nhật `expected_duration` động cho QA checker và truyền đúng metadata `sese_applied` cùng `added_duration` sang Review Service để tránh bị đánh fail hoặc trừ điểm oan.
4. **Mặc định tắt khi rollout:** Khởi tạo `sese_enabled = False` làm mặc định để đảm bảo an toàn tuyệt đối.
