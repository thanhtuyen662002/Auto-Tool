# Auto Tool Studio - Windows Launcher

## Chạy app

Double-click `start_auto_tool_studio.bat`. Launcher sẽ kiểm tra môi trường, tạo `.venv`, cài package còn thiếu, build frontend khi cần và mở:

```txt
http://127.0.0.1:8000
```

Cửa sổ `Auto Tool Studio Server` phải được giữ mở. Đóng cửa sổ đó để tắt app.

## Nếu app không mở

1. Double-click `check_system.bat`.
2. Sửa các mục `[ERROR]` được báo.
3. Chạy `start_auto_tool_studio_debug.bat` để xem lỗi trực tiếp.
4. Xem log mới nhất trong `logs/launcher/`.

## Công cụ đi kèm

- `check_system.bat`: chỉ kiểm tra, không start app.
- `build_frontend.bat`: cài package frontend và build lại UI.
- `reset_local_app_cache.bat`: backup rồi xóa recent folders; không xóa output, database, source video hoặc project.

## Yêu cầu

- Python 3.11 trở lên.
- Node.js LTS khi cần build frontend lần đầu.
- FFmpeg/ffprobe. Auto Tool cũng có thể dùng runtime được tải về thư mục app data.

## Lỗi thường gặp

### Không tìm thấy Python

Cài Python 3.11+, tick `Add Python to PATH`, đóng cửa sổ launcher và chạy lại.

### Không tìm thấy Node.js

Cài Node.js LTS. Nếu `frontend/dist` đã có, app vẫn chạy được mà không cần Node.

### FFmpeg missing

App vẫn mở được nhưng render video sẽ lỗi cho đến khi FFmpeg runtime được chuẩn bị.

### Port 8000 đang bận

Thử mở `http://127.0.0.1:8000`. Nếu đó không phải Auto Tool, đóng chương trình đang dùng cổng này. Launcher không tự kill tiến trình.

### Build frontend thất bại

Chạy `build_frontend.bat` để xem lỗi TypeScript/Vite đầy đủ.

## Tạo shortcut Desktop

Click chuột phải `start_auto_tool_studio.bat`, chọn `Send to` rồi `Desktop (create shortcut)`.
