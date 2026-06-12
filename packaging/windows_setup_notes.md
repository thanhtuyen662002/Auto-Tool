# Windows setup notes

1. Cài Python 3.11+ và Node.js LTS, chọn tùy chọn thêm vào `PATH`.
2. Double-click `launcher\check_system.bat` để kiểm tra.
3. Double-click `launcher\start_auto_tool_studio.bat` để chạy app.
4. Nếu Windows Firewall hỏi, chỉ cho phép mạng Private. App mặc định chỉ bind `127.0.0.1`.
5. Có thể build EXE bằng PowerShell: `powershell -ExecutionPolicy Bypass -File packaging\build_windows_exe.ps1`.

FFmpeg/ffprobe nên có trong `PATH`. Launcher và dependency manager của dự án vẫn tiếp tục kiểm tra runtime dependencies khi app khởi động.

Nếu launcher lỗi, chạy `launcher\start_auto_tool_studio_debug.bat` và xem log trong `logs\launcher\`.
