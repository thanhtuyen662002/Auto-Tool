# Local App Packaging QA Checklist

## Bootstrap

- [ ] `config/local_app_config.json` được tự tạo khi thiếu.
- [ ] Cấu hình JSON lỗi được backup và phục hồi về mặc định.
- [ ] Output folder mặc định được tạo và có quyền ghi.
- [ ] Frontend build được phục vụ từ backend local.

## Scripts

- [ ] `start_dev` khởi động backend và Vite frontend.
- [ ] `start_local_app` chuẩn bị môi trường và mở app local.
- [ ] `build_frontend` tạo `frontend/dist/index.html`.
- [ ] `check_system` báo Python, Node/npm, FFmpeg và ffprobe.

## UI

- [ ] Settings > Local App tải, lưu và reset cấu hình.
- [ ] System check hiển thị dependency bắt buộc và tùy chọn.
- [ ] Start Workflow dùng recent paths từ backend và fallback localStorage.
- [ ] Results có thể Copy Path, Open Folder và Reveal File.
- [ ] Backend offline banner có nút kiểm tra lại và mở hướng dẫn.

## Security

- [ ] Backend mặc định bind `127.0.0.1`.
- [ ] Open Folder có thể tắt trong Settings.
- [ ] Desktop commands không sử dụng `shell=True`.
- [ ] Không lưu secret trong config hoặc recent paths.

## Platform

- [ ] Windows scripts được chạy thực tế.
- [ ] macOS scripts được syntax-check/chạy trên macOS.
- [ ] Linux scripts được syntax-check/chạy trên Linux.
