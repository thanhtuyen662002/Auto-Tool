# Báo cáo Khoảng cách Công nghệ (Modernization Gaps Report)

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Liệt kê các khoảng cách công nghệ giữa workflow Affiliate hiện tại so với các module mới và các tính năng hiện đại cần có để đạt trải nghiệm tối ưu.

---

## 1. Các Khoảng cách Công nghệ chính (Major Gaps)

Mặc dù workflow Affiliate đang chạy trên một pipeline kết xuất tương đối hiện đại và tích hợp nhiều thành phần thông minh, quy trình này vẫn tồn tại 4 khoảng cách công nghệ chính cần được cải tiến:

### Gap 1: Chưa hỗ trợ Ảnh tĩnh làm Clip nguồn trong Timeline
*   **Trạng thái hiện tại:** `MediaScanner` và `Renderer` chỉ chấp nhận các tệp tin video (`.mp4`, `.mkv`, v.v.). Nếu người dùng chỉ có hình ảnh chụp sản phẩm từ Shopee, họ không thể đưa chúng làm tư liệu chạy timeline dựng video.
*   **Hệ quả:** Người dùng bắt buộc phải có sẵn video tự quay hoặc tự tải về máy. Đối với người làm affiliate dropshipping chưa sở hữu sản phẩm vật lý để tự quay, đây là một rào cản lớn.
*   **Tác động:** Trung bình - Cao.

### Gap 2: Thiếu Trình dựng Timeline trực quan (Visual Timeline Editor)
*   **Trạng thái hiện tại:** Timeline được sinh hoàn toàn tự động bởi thuật toán `ProductTimelineBuilder` dựa trên các slot cố định của Timeline Template. Người dùng không có cách nào điều chỉnh thứ tự, thêm bớt clip hoặc thay thế một clip cụ thể bằng kéo thả trên UI.
*   **Hệ quả:** Nếu thuật toán tự động chọn một cảnh quay không ưng ý, người dùng chỉ có cách đổi trạng thái review của cảnh quay đó (exclude/favorite) rồi chạy dựng lại toàn bộ timeline, không thể sửa đổi cục bộ.
*   **Tác động:** Cao (ảnh hưởng trực tiếp đến trải nghiệm biên tập).

### Gap 3: Chỉ hỗ trợ Giọng thuyết minh đơn (Single-speaker TTS)
*   **Trạng thái hiện tại:** `VoiceGenerator` gọi TTS để sinh một file audio duy nhất cho toàn bộ video bằng một giọng đọc duy nhất (Single Voice ID).
*   **Hệ quả:** Không thể tạo các video dạng đối thoại, phỏng vấn, kịch bản đóng vai (roleplay) giữa nhiều nhân vật khác nhau (ví dụ: Người bán và Người mua, Vợ và Chồng) vốn là các định dạng video bán hàng rất viral trên TikTok/Shopee.
*   **Tác động:** Trung bình.

### Gap 4: Thiếu Tính năng Nhân bản Dự án nhanh (Duplicate Project)
*   **Trạng thái hiện tại:** Hệ thống quản lý dự án chưa cung cấp nút "Duplicate" trên UI hoặc API.
*   **Hệ quả:** Khi muốn chạy A/B testing kịch bản khác nhau cho cùng một sản phẩm và cùng thư mục video nguồn, người dùng phải tạo lại dự án từ đầu và điền lại toàn bộ thông tin sản phẩm và cấu hình render thủ công.
*   **Tác động:** Thấp - Trung bình.

---

## 2. Bảng đối chiếu Tích hợp Tính năng hiện đại

| Module hiện đại | Trạng thái tích hợp | Ghi chú |
|-----------------|---------------------|---------|
| **Smart Segment Scoring** | **YES** | Tích hợp tốt, chạy tự động chấm điểm contrast, blur, motion thô. |
| **Product-aware Templates**| **YES** | Đã tích hợp 4 template tỉ lệ phân chia theo cảnh thuyết minh. |
| **Script Variant Generator**| **YES** | Tích hợp tốt qua Gemini sinh 6 phong cách kịch bản. |
| **Source Media Browser** | **YES** | Tích hợp tốt, hỗ trợ review, favorite, exclude cảnh trên UI. |
| **Queue Control** | **YES** | Tích hợp tốt, quản lý tiến trình render hàng loạt qua Queue State. |
| **Crash Recovery** | **YES** | Tích hợp tốt, tự động khôi phục từ checkpoint gián đoạn. |
| **Subtitle Translation Engine**| **NO** | Không cần tích hợp vì kịch bản được viết bằng tiếng Việt trực tiếp từ đầu. |
