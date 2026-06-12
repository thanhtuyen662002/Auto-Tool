# Navigation, Settings & Onboarding QA Checklist

Prompt 50 scope: Navigation, Settings, System Status, Onboarding, First Run Experience, Help and Empty States.

- [x] Sidebar chỉ có mục lớn, không rối
- [x] Active route hiển thị rõ
- [x] Top bar hiển thị page title đúng
- [x] Dashboard có workflow cards rõ
- [x] First Run Checklist hiển thị khi chưa có project hoặc khi mở Onboarding
- [x] System Status hiển thị backend/FFmpeg/OCR/TTS
- [x] Settings page chia section rõ
- [x] Path settings lưu localStorage được
- [x] Appearance settings áp dụng được
- [x] Advanced settings mặc định đóng
- [x] Help page có hướng dẫn workflow
- [x] Onboarding page mở được
- [x] Onboarding có thể bỏ qua
- [x] Recent folders/projects fallback không crash
- [x] Backend offline có message thân thiện
- [x] Technical logs mặc định ẩn
- [x] UI không vỡ trên laptop nhỏ
- [x] UI không tràn ngang trên mobile
- [x] Frontend build không lỗi

Notes:
- Browser QA đã chạy trên `/`, `/settings`, `/help`, `/onboarding`.
- Đã kiểm tra command center, system status modal, settings tabs, appearance class, advanced drawer và responsive 1024x768 + 390x844.
- Path settings đã test thao tác Save với giá trị hiện có. Browser runtime không cho nhập text bằng Playwright/CUA do thiếu virtual clipboard, nên không dùng được để test typing path thủ công trong phiên QA này.
- Chưa bấm chạy job thật trong QA UI để tránh tạo pipeline xử lý video ngoài ý muốn.
