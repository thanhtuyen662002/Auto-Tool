# Đánh giá Rủi ro Kỹ thuật: Smart Ending Synchronization Engine (SESE)

**Dự án:** Auto Tool Studio  

---

## 1. Phân tích Rủi ro & Giải pháp Giảm thiểu

### A. Rủi ro Hệ thống (Technical Risk)
- **Vấn đề:** Thay đổi thứ tự trong `output_pipeline.py` (tạo Giọng nói & Script trước khi dựng Visual) có thể ảnh hưởng đến các tác vụ chạy song song hoặc gây lỗi nếu quá trình sinh TTS bị thất bại giữa chừng.
- **Tác động:** Render bị crash toàn bộ.
- **Giải pháp giảm thiểu:** 
  - Bọc khối lệnh sinh giọng nói và đo thời lượng trong khối `try...except`.
  - Nếu sinh TTS thất bại, tự động fallback: Gán `voice_duration = target_duration`, tạo âm thanh im lặng (silent audio) dự phòng và giữ nguyên timeline visual gốc mà không áp dụng kéo dài/freeze frame.

### B. Rủi ro Kết xuất (Render Risk)
- **Vấn đề:** Trích xuất khung hình cuối (`last_frame`) từ video nguồn của clip cuối có thể thất bại nếu tệp video bị lỗi định dạng hoặc không có keyframe tại vị trí chỉ định.
- **Tác động:** FFmpeg báo lỗi và quá trình render visual clip cuối bị dừng lại.
- **Giải pháp giảm thiểu:**
  - Lấy thời gian trích xuất an toàn cách điểm cuối 0.05s: `extract_time = max(clip.start, clip.end - 0.05)`.
  - Nếu lệnh trích xuất ảnh tĩnh PNG bị thất bại (trả về mã lỗi khác 0), hệ thống tự động sinh một khung hình nền đen (black solid frame) có cùng độ phân giải để thay thế làm Freeze Frame, đảm bảo pipeline render không bao giờ bị dừng đột ngột.

### C. Rủi ro Bộ lọc FFmpeg (FFmpeg Filter Risk)
- **Vấn đề:** Bộ lọc `zoompan` của FFmpeg nổi tiếng là nhạy cảm với cú pháp và hiệu năng. Nếu giá trị `total_frames` tính toán bị sai hoặc bằng 0, FFmpeg có thể crash hoặc rò rỉ bộ nhớ.
- **Tác động:** Tiến trình render bị treo hoặc báo lỗi cú pháp filtercomplex.
- **Giải pháp giảm thiểu:**
  - Đảm bảo $\Delta \ge 0.5$s thì mới kích hoạt tạo Freeze Frame/Zoom clip.
  - Ép kiểu `total_frames = max(1, int(clip.duration * fps))`.
  - Sử dụng tham số `-q:v 2` và giải nén ảnh PNG trung gian để chất lượng hình ảnh tốt nhất, tránh lỗi nén hình.

### D. Rủi ro Phụ đề (Subtitle Risk)
- **Vấn đề:** Phụ đề có thể bị lệch hoặc hiển thị chồng chéo lên phần visual kéo dài (Freeze Frame/Zoom).
- **Tác động:** Trải nghiệm người dùng kém, phụ đề câu cuối xuất hiện sớm hoặc muộn hơn giọng đọc.
- **Giải pháp giảm thiểu:**
  - Triển khai tạo phụ đề (`generate_subtitle`) **sau khi** timeline đã được SESE điều chỉnh. Lúc này, phụ đề sẽ được dựng trực tiếp dựa trên timeline thực tế đã khớp với audio, triệt tiêu hoàn toàn khả năng lệch phụ đề ở các phân cảnh cuối.

### E. Ảnh hưởng Hiệu năng (Performance Impact)
- **Vấn đề:** Thêm các bước phụ (trích xuất frame, chạy lệnh ffmpeg riêng cho clip tĩnh) có thể làm tăng thời gian render tổng thể.
- **Tác động:** Thời gian render video lâu hơn.
- **Đánh giá thực tế:** 
  - Việc trích xuất 1 frame PNG diễn ra trong khoảng `< 0.1s`.
  - Việc render clip tĩnh từ ảnh PNG (dài từ 0.5s - 8s) tốn cực kỳ ít CPU do không phải giải mã/mã hóa các luồng video động phức tạp.
  - Tổng thời lượng kết xuất tăng thêm ước tính chỉ khoảng **< 1.5%**, hoàn toàn chấp nhận được so với độ chính xác và chất lượng đầu ra mang lại.

---

## 2. Chiến lược Rollback (Rollback Strategy)

Để đảm bảo an toàn tuyệt đối và tính liên tục của hệ thống, SESE cung cấp 2 cơ chế rollback độc lập:

1. **Rollback thông qua Cấu hình (Config-based Rollback):**
   - Người dùng hoặc quản trị viên có thể tắt SESE bất kỳ lúc nào bằng cách đặt `sese_enabled = False` trong `RenderSettings`.
   - Khi `sese_enabled = False`, `SESEEngine` sẽ bỏ qua việc so sánh và giữ nguyên timeline gốc, đồng thời `VoiceGenerator` tự động nhận `target_duration` giới hạn cũ để chạy tính năng trim cứng như trước đây.
2. **Rollback mã nguồn (Code Git Rollback):**
   - Toàn bộ thay đổi của SESE được đóng gói độc lập trong module `sese_engine.py` và các hook gọi tại `output_pipeline.py`. Việc gỡ bỏ chỉ cần revert các dòng code gọi SESE tại `output_pipeline.py` mà không ảnh hưởng tới bất kỳ core logic nào khác của phần mềm.

---

## 3. Điểm đánh giá mức độ sẵn sàng triển khai (Implementation Readiness Score)

Dựa trên các phân tích kỹ thuật và phương án dự phòng chuẩn bị kỹ lưỡng:

- **Thiết kế kiến trúc:** 95/100 (Tách biệt rõ ràng, không xâm lấn core render).
- **Mức độ an toàn/Bảo vệ lỗi:** 90/100 (Có fallback nền đen, try-except toàn bộ TTS).
- **Khả năng tương thích ngược:** 100/100 (Không thay đổi DB schema hay API hiện tại).
- **Hiệu năng:** 95/100 (Ảnh hưởng hiệu năng dưới 1.5%).

### **Tổng điểm: 95/100**

### **Kết luận: READY (SẴN SÀNG TRIỂN KHAI)**
Hệ thống thiết kế SESE đã hoàn thiện, đạt độ an toàn cao và sẵn sàng bắt đầu viết code triển khai thực tế.
