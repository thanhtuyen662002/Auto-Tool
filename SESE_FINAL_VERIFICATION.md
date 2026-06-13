# Báo cáo Kiểm chứng & Tinh chỉnh Kiến trúc Cuối cùng trước Triển khai: SESE

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Đảm bảo không tích tụ technical debt và bảo toàn tính toàn vẹn của render pipeline trước khi tiến hành code B7.

---

## 1. Timeline Persistence Audit

### Câu hỏi & Trả lời:
- **Kiểm tra timeline có được hash, serialize, snapshot hoặc cache ở đâu không?**
  - **Có.** Trong `output_pipeline.py`, hàm `_timeline_report` serialize đối tượng `timeline` thành JSON và ghi vào `{name}_timeline.json`.
  - **Có.** Trong `render_worker.py`, `CropSafetyService.analyze_timelines()` quét qua các timeline để tính điểm an toàn khung hình và lưu báo cáo trước khi render.
- **Tác động của SESE:**
  - SESE chỉ điều chỉnh clip cuối cùng của timeline (kéo dài hoặc chèn clip tĩnh mới).
  - Để tránh việc chạy lại OpenCV để quét crop safety cho clip freeze frame mới (gây lãng phí CPU), clip mới sẽ sao chép trực tiếp các trường metadata an toàn (`crop_box`, `crop_mode`, `crop_safety_score`) từ clip liền trước nó.
- **Xác nhận luồng truyền dữ liệu:**
  - Đối tượng timeline đã qua xử lý SESE (`adjusted_timeline`) sẽ được truyền trực tiếp vào `renderer.render_timeline` và tất cả các hàm helper ghi log, QA Checker phía sau. Điều này đảm bảo tính nhất quán và không có nơi nào sử dụng lại timeline thô ban đầu.

---

## 2. Clip Type Refactor Review

### So sánh hai phương án thiết kế cấu trúc dữ liệu:

* **Phương án A (Hai cờ Boolean):**
  ```python
  freeze_frame: bool = False
  slow_zoom: bool = False
  ```
* **Phương án B (Trường trạng thái Clip Type):**
  ```python
  clip_type: str = "normal"  # "normal", "freeze", "freeze_zoom"
  ```

### Đánh giá các tiêu chí kỹ thuật:

| Tiêu chí | Phương án A (Boolean Flags) | Phương án B (Clip Type Enum) |
| :--- | :--- | :--- |
| **Maintainability** | **6/10** (Dễ bị trạng thái không hợp lệ, ví dụ `freeze_frame=False` nhưng `slow_zoom=True`) | **9.5/10** (Trạng thái loại trừ lẫn nhau, không bao giờ xung đột dữ liệu) |
| **Extensibility** | **6/10** (Thêm hiệu ứng mới phải thêm cột boolean mới vào schema) | **9.5/10** (Dễ dàng mở rộng thêm các kiểu như `solid_color`, `title_card`) |
| **Schema Clarity** | **7/10** (Nhiều cờ boolean gây rối mắt khi đọc schema JSON) | **9.5/10** (Chỉ 1 trường duy nhất xác định rõ kiểu clip và luồng render) |

### **Khuyến nghị cuối cùng:**
**Chọn Phương án B (`clip_type`).** Đây là thiết kế tối ưu nhất giúp giảm thiểu nợ kỹ thuật (technical debt), làm sạch schema và thuận tiện mở rộng các hiệu ứng clip visual đặc biệt sau này.

---

## 3. SESE Guard Strategy

Bên cạnh giới hạn tuyệt đối `max_auto_extension_seconds` (giây), việc bổ sung `max_auto_extension_ratio` (tỷ lệ phần trăm) là **BẮT BUỘC** để tránh việc chèn các đoạn đóng băng hình quá dài lên các video ngắn (ví dụ: video gốc 6 giây nhưng freeze frame tận 8 giây, chiếm > 130% thời lượng video, gây nhàm chán cho người xem).

### Công thức Guard Tối ưu:
$$\text{max\_allowed\_extension} = \min(\text{max\_auto\_extension\_seconds}, \text{max\_auto\_extension\_ratio} \times \text{target\_duration})$$

* **Giá trị mặc định đề xuất:**
  * `max_auto_extension_seconds = 8.0` (giây)
  * `max_auto_extension_ratio = 0.4` (40% thời lượng video mục tiêu)
* **Ví dụ áp dụng:**
  * Video mục tiêu 12s: $\min(8.0, 0.4 \times 12) = \min(8.0, 4.8) \Rightarrow$ Cho phép kéo dài tối đa **4.8s**.
  * Video mục tiêu 30s: $\min(8.0, 0.4 \times 30) = \min(8.0, 12.0) \Rightarrow$ Cho phép kéo dài tối đa **8.0s**.

---

## 4. Failure Strategy Review

Khi thời lượng chênh lệch vượt quá giới hạn an toàn tối đa ($\Delta > \text{max\_allowed\_extension}$):

* **Phương án A (Fallback trim voice):** Cắt bớt phần âm thanh thừa để khớp với giới hạn video tối đa. Video vẫn render thành công nhưng bị cụt câu cuối.
* **Phương án B (Hard fail + warning + preserve voice):** Đánh dấu lỗi (FAIL) tiến trình render, không xuất bản video hỏng để bảo toàn nội dung kịch bản thoại.

### Đánh giá sự phù hợp:
Mục tiêu ban đầu của SESE là **bảo toàn nội dung giọng nói**. Việc tự động trim voice (Phương án A) trực tiếp đi ngược lại mục tiêu này. Tuy nhiên, việc đánh FAIL hoàn toàn (Phương án B) có thể làm đứt gãy luồng xử lý tự động hàng loạt của người dùng.

### **Khuyến nghị cuối cùng:**
Cung cấp tùy chọn cấu hình `sese_failure_strategy: str = "trim"` (mặc định là `"trim"` để tương thích ngược và chạy mượt mà, nhưng cho phép người dùng cấu hình thành `"fail"` để chủ động kiểm soát chất lượng kịch bản).
- Khi strategy là `"trim"`: Áp dụng trim voice tại giới hạn tối đa kèm QA Warning `voice_cut_detected`.
- Khi strategy là `"fail"`: Báo lỗi render job ngay lập tức kèm thông báo lỗi chi tiết.

---

## 5. Bản Đánh giá Pre-Implementation gốc (B6.6)

*(Giữ lại các thông tin xác thực từ audit trước để tham chiếu)*

### A. Xác thực Voice Cache (Voice Cache Validation)
- Cache key sử dụng thuật toán băm SHA-1 trên payload thông số TTS.
- Việc đặt `target_duration = 0.0` dưới SESE sẽ sinh cache key mới an toàn, không gây xung đột cache (collisions).

### B. Nguồn dữ liệu Phụ đề (Subtitle Truth Source)
- Phụ đề co giãn theo tỷ lệ ký tự trên tổng thời lượng `voice_duration`.
- Hệ thống không sử dụng word alignment của audio nhưng SESE sẽ giúp loại bỏ phụ đề mồ côi (ghost subtitles) do giọng nói bị cắt.

### C. Độ quan trọng của Review Service (Review Service Criticality)
- Review Service chạy độc lập sau render nên thuộc dạng `OPTIONAL` (không ảnh hưởng trực tiếp tới thành bại của việc tạo tệp MP4).

---

# **KẾT LUẬN CUỐI CÙNG: APPROVE FOR B7 (PHÊ DUYỆT BẮT ĐẦU CODE B7)**
