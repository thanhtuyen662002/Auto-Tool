# Báo cáo Đánh giá Tác động Phụ thuộc: SESE (SESE Dependency Audit)

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Kiểm tra và phân tích toàn bộ đồ thị phụ thuộc của hệ thống thời lượng (duration) để đảm bảo việc thay đổi luồng xử lý và kéo dài video cuối của SESE không phá vỡ bất kỳ tính năng nào đang hoạt động.

---

## PART 1 — Dependency Graph Audit

Dưới đây là sơ đồ phân tích các module phụ thuộc trực tiếp hoặc gián tiếp vào cấu hình thời lượng (`render.duration`, `timeline.duration`, `voice_duration`, `subtitle timing`, và `output duration`).

### Phân loại các Module

#### A. Các Module thực thi trước Render
1. **[ScriptWriter](file:///d:/Projects/Auto-Tool/backend/app/modules/script_writer/script_writer.py):** Sinh câu thoại kịch bản dựa trên `config.render.duration` (tính toán số câu khuyến nghị).
2. **[ProductTimelineBuilder](file:///d:/Projects/Auto-Tool/backend/app/modules/timeline_builder/timeline_builder.py):** Dựng timeline clips visual với tổng thời lượng khớp tĩnh với `config.render.duration`.

#### B. Các Module thực thi sau Render
1. **[OutputQualityReviewService](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py):** Chấm điểm chất lượng kỹ thuật, âm thanh và phụ đề của tệp video MP4 kết quả.
2. **[QA Checker](file:///d:/Projects/Auto-Tool/backend/app/modules/qa_checker/qa_checker.py):** Kiểm định độ phân giải, luồng âm thanh, phụ đề và so sánh độ dài tệp thực tế với thời lượng đích.

#### C. Các Module giả định thời lượng video là cố định (Fixed Duration)
1. **[Preview Mode Configuration](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/render_worker.py):** Ép cứng thời lượng preview tối đa là 8 giây (`min(config.render.duration, 8.0)`).
2. **[SubtitleGenerator](file:///d:/Projects/Auto-Tool/backend/app/modules/subtitle_generator/subtitle_generator.py):** Giả định `target_video_duration` là điểm neo cứng để giới hạn mốc kết thúc của toàn bộ phụ đề.

#### D. Các Module có thể bị lỗi (Break) nếu Video kết quả dài hơn `config.render.duration`
1. **QA Checker (`_check_duration`):** Báo lỗi FAIL nếu độ lệch video thực tế và `config.render.duration` vượt quá 2 giây.
2. **OutputQualityReviewService (`_technical_score` & `_audio_score`):** Trừ điểm nặng (-0.2 và -0.3 điểm) nếu thời lượng thực tế lệch quá 2 giây so với cấu hình.

---

### Bảng Phân tích Chi tiết Tác động Phụ thuộc

| File | Function | Dependency | Risk Level | Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| [output_pipeline.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/output_pipeline.py) | `render_one_output` | `config.render.duration` truyền vào QA Checker | **HIGH** | Truyền thời lượng *đã điều chỉnh* (adjusted duration) của SESE vào `check_output_video` thay vì `config.render.duration`. |
| [qa_checker.py](file:///d:/Projects/Auto-Tool/backend/app/modules/qa_checker/qa_checker.py) | `_check_duration` | So sánh độ dài video thực tế với `expected_duration` | **HIGH** | Không sửa code của QA checker. Chỉ cần thay đổi tham số `expected_duration` truyền từ pipeline thành thời lượng đã SESE cân bằng. |
| [review_service.py](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py) | `_technical_score` | Kiểm tra độ lệch giữa video MP4 thực tế và `config.render.duration` (> 2s) | **HIGH** | Ghi nhận trường `sese_applied` và `added_duration` vào output metadata. Chỉnh sửa hàm `_technical_score` để nếu `sese_applied=True` thì cộng thêm `added_duration` vào thời lượng so sánh. |
| [review_service.py](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py) | `_audio_score` | So sánh `voice_duration` với `config.render.duration` (> 2s) | **HIGH** | Tương tự trên, sử dụng `config.render.duration + added_duration` làm mốc so sánh khi `sese_applied=True`. |
| [render_worker.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/render_worker.py) | `_preview_config` | Ghi đè `duration` thành tối đa 8.0s cho chế độ Preview | **MEDIUM** | **Bypass SESE khi chạy Preview.** Force đặt `sese_enabled = False` trong `_preview_config` để tránh kéo dài video preview ngoài ý muốn. |

---

## PART 2 — Subtitle Synchronization Audit

1. **Subtitle timestamps được tạo từ nguồn nào?**
   - Subtitle timestamps được tạo dựa vào cấu trúc **kịch bản (character length weights)** và co giãn tương đối theo biến `active_duration` (độ dài âm thanh hoạt động) thông qua hàm `build_subtitle_timeline`.
2. **Nếu SESE kéo dài video cuối:**
   - *Subtitle timing có bị lệch (drift) không?* **Không.** Vì toàn bộ timeline phụ đề sẽ được tính toán co giãn theo thời lượng giọng nói thực tế trước khi xuất file SRT/ASS, và visual cũng khớp 100% với thời lượng này.
   - *Subtitle có biến mất sớm không?* **Không.** Khoảng thời gian hoạt động của phụ đề kéo dài đến hết audio, hình ảnh kéo dài tương ứng nên phụ đề hiển thị trọn vẹn đến câu cuối cùng.
3. **Quá trình sinh phụ đề đã dựa trên voice chưa?**
   - **Rồi.** Hàm `_active_duration` trong `SubtitleGenerator` nhận và sử dụng `voice_duration` để giới hạn mốc kết thúc phụ đề.
4. **Hàm sinh phụ đề có thể giữ nguyên không?**
   - **Có.** Không cần sửa đổi bất kỳ logic nào trong `subtitle_generator.py`. Chỉ cần truyền chính xác tham số `target_video_duration` đã được SESE cập nhật vào các hàm `generate_srt` và `generate_ass`.

**Kết luận Subtitle:** **SAFE**. Subtitle generator tương thích hoàn hảo với thiết kế SESE.

---

## PART 3 — Job Recovery Impact

### A. Khôi phục tiến trình (Job Resume)
- **Tác động:** Khi resume một Job bị gián đoạn, hệ thống đọc lại snapshot ProjectConfig đã lưu ở SQLite.
- **Đánh giá:** **SAFE**. Vì cấu hình SESE (`sese_enabled`, `max_auto_extension_seconds`) được lưu trực tiếp trong ProjectConfig snapshot, các output render tiếp theo khi resume sẽ áp dụng nhất quán đúng logic SESE mà không bị lệch cấu hình.

### B. Lưu trữ thời lượng (Persisted Durations)
- **Tác động:** Bảng dữ liệu SQLite của jobs chỉ lưu trữ đường dẫn file và trạng thái hoàn thành, không bắt buộc độ dài cứng. Quá trình kiểm tra file tồn tại (`check_output_exists_and_valid`) chỉ yêu cầu `duration > 0`.
- **Đánh giá:** **SAFE**. Không có ràng buộc thời lượng tĩnh nào trong DB.

### C. Bộ nhớ đệm (Cache Invalidations)
- **Tác động:** Cache giọng nói TTS sử dụng tham số `target_duration` trong cache key.
- **Đánh giá:** **SAFE**. Khi SESE bật, `target_duration` truyền vào Voice Generator luôn là `0.0` (untrimmed), đảm bảo cache key nhất quán tuyệt đối giữa các lần chạy và lần khôi phục.

| Recovery Path | Safety Status | Reason |
| :--- | :--- | :--- |
| **Resume Candidate Discovery** | **SAFE** | Chỉ quét trạng thái job, không quét dữ liệu thời lượng. |
| **Job Reconciliation** | **SAFE** | Chỉ xác thực file tồn tại và ffprobe `duration > 0`. |
| **Job Lock & Checkpoints** | **SAFE** | Khôi phục đúng ProjectConfig snapshot chứa setting SESE. |
| **Cache Hits** | **SAFE** | Cache key thống nhất do target_duration = 0.0 cố định. |

---

## PART 4 — Preview Mode Impact

- **Sinh giọng nói trong Preview:** Chế độ Preview vẫn thực hiện chạy sinh giọng nói đầy đủ để người dùng kiểm tra âm thanh.
- **Phụ thuộc thời lượng cố định:** Có. Preview ép cứng thời lượng visual tối đa là 8.0s để render nhanh.
- **Ảnh hưởng của SESE đến Preview:** Nếu SESE hoạt động trong chế độ Preview, nó sẽ cố gắng kéo dài timeline visual lên 15s-20s theo giọng nói thực tế, làm mất tác dụng render nhanh của Preview.
- **Đánh giá Preview Mode:** **WARNING**. 

**Mitigation:** Cần vô hiệu hóa SESE (`sese_enabled = False`) một cách cưỡng bức trong hàm tạo cấu hình preview `_preview_config` tại `render_worker.py`.

---

## PART 5 — QA Checker Impact

Nếu giữ nguyên QA checker và review service không sửa đổi, các quy tắc sau sẽ báo lỗi **FAIL** hoặc trừ điểm nặng:

1. **Lỗi `_check_duration` trong `qa_checker.py`:**
   - *Vị trí:* [qa_checker.py dòng 108-119](file:///d:/Projects/Auto-Tool/backend/app/modules/qa_checker/qa_checker.py#L108-L119)
   - *Nguyên nhân:* So sánh độ lệch giữa video thực tế (ví dụ 16.3s) và `expected_duration` (truyền tĩnh là 12s). Độ lệch 4.3s vượt quá ngưỡng cảnh báo 2s nên QA checker đánh lỗi `duration failed`, làm job bị đánh dấu `failed`.
2. **Trừ điểm `_technical_score` trong `review_service.py`:**
   - *Vị trí:* [review_service.py dòng 252-253](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py#L252-L253)
   - *Nguyên nhân:* Trừ 0.2 điểm nếu độ lệch video thực tế và `config.render.duration` > 2 giây.
3. **Trừ điểm `_audio_score` trong `review_service.py`:**
   - *Vị trí:* [review_service.py dòng 291-295](file:///d:/Projects/Auto-Tool/backend/app/modules/output_review/review_service.py#L291-L295)
   - *Nguyên nhân:* Giới hạn điểm tối đa còn 0.55 hoặc 0.7 nếu `voice_duration` lệch quá 2s - 4s so với `config.render.duration`.

---

## PART 6 — Final Readiness Score

- **Architecture Safety Score:** `92/100` (Kiến trúc cực kỳ an toàn, phân tách trách nhiệm tốt, không thay đổi DB hay API core).
- **Integration Complexity:** `Low` (Chỉ cần can thiệp luồng gọi tại `output_pipeline.py` và bổ sung xử lý freeze frame tại `renderer.py`).
- **Rollback Difficulty:** `Low` (Có thể tắt SESE ngay lập tức bằng flag cấu hình `sese_enabled = False`).

### Khuyến nghị cuối cùng: **B. Implement SESE with safeguards (Triển khai SESE kèm các biện pháp bảo vệ)**

**Lý do:**  
Kiến trúc SESE đã sẵn sàng và rất an toàn. Tuy nhiên, để tránh việc kéo dài video preview làm chậm hệ thống và tránh bị QA Checker / Review Service đánh lỗi/trừ điểm sai lệch thời lượng, chúng ta bắt buộc phải triển khai 3 biện pháp bảo vệ đi kèm:
1. Ép cứng tắt SESE khi chạy Preview.
2. Truyền thời lượng sau SESE (adjusted duration) làm expected duration cho QA Checker.
3. Ghi nhận `sese_applied` và `added_duration` vào log để Review Service nhận biết và không trừ điểm oan.
