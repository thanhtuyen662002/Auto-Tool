# Subtitle Review Editor UI QA Checklist

- [x] Mở được danh sách review documents.
- [x] Mở được editor từ document card.
- [x] Video preview tải được hoặc hiển thị fallback rõ ràng.
- [x] Click subtitle line seek video đúng timing.
- [x] Active line highlight rõ.
- [x] Sửa text không lag và textarea tự thay đổi chiều cao.
- [x] Save current line hoạt động.
- [x] Save all hoạt động.
- [x] Badge `Chưa lưu` hiển thị và biến mất đúng lúc.
- [x] Filter `Cần kiểm tra` hoạt động.
- [x] Filter `Lỗi nặng` hoạt động.
- [x] Search phụ đề hoạt động.
- [x] Sort timeline/quality/edited/critical có trong UI.
- [x] Next flagged line hoạt động.
- [x] Suggest Rewrite mở panel đúng.
- [x] Apply suggestion cập nhật text.
- [x] Approve modal cảnh báo nếu còn critical.
- [x] Render button rõ và disabled khi chưa approve.
- [x] Technical log mặc định ẩn và mở bằng menu phụ.
- [x] Phím tắt hiển thị trong modal help.
- [x] Textarea dễ đọc và gần solid.
- [x] Mobile/laptop nhỏ không vỡ layout.
- [x] Frontend build không có TypeScript error.

Ghi chú QA: không bấm `Approve anyway` hoặc `Render video` trong lần kiểm tra này để tránh đổi trạng thái tài liệu sample hoặc tạo job render mới.
