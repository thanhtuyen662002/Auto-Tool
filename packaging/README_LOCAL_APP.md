# Auto Tool Local App

Auto Tool có thể chạy như một ứng dụng local mà không cần Electron hoặc Tauri. Backend FastAPI phục vụ cả API và frontend đã build trên một địa chỉ localhost.

## Chạy nhanh

### Windows

```bat
scripts\start_local_app.bat
```

### macOS / Linux

```bash
chmod +x scripts/*.sh
./scripts/start_local_app.sh
```

Lần chạy đầu sẽ tạo `.venv`, cài Python packages, cài Node packages khi cần và build frontend. Cấu hình được tạo tại `config/local_app_config.json`.

## Windows one-click launcher

Mở folder `launcher/` và double-click `start_auto_tool_studio.bat`. Launcher sẽ tự kiểm tra môi trường, chuẩn bị `.venv`, cài package, build frontend khi cần và mở `http://127.0.0.1:8000`.

Nếu có lỗi:

- Chạy `launcher/check_system.bat`.
- Chạy `launcher/start_auto_tool_studio_debug.bat`.
- Gửi file log mới nhất trong `logs/launcher/`.

Xem hướng dẫn đầy đủ tại `launcher/README_WINDOWS_LAUNCHER.md`.

## Chế độ phát triển

- Windows: `scripts\start_dev.bat`
- macOS/Linux: `./scripts/start_dev.sh`
- Kiểm tra máy: `scripts\check_system.bat` hoặc `./scripts/check_system.sh`
- Chỉ build frontend: `scripts\build_frontend.bat` hoặc `./scripts/build_frontend.sh`

## Chạy production một cổng

Windows:

```bat
scripts\start_local_prod.bat
```

macOS/Linux:

```bash
./scripts/start_local_prod.sh
```

Sau khi khởi động, mở `http://127.0.0.1:8000`. Backend phục vụ cả React production build và API `/api` trên cùng cổng.

## Dev mode và Production mode

Dev mode dùng backend cổng `8000` và Vite cổng `5173`, phù hợp khi chỉnh UI và cần hot reload. Vite proxy `/api` về backend.

Production local mode chỉ dùng `http://127.0.0.1:8000`, không cần chạy Vite. Đây là chế độ dùng hằng ngày và khi đóng gói local app.

## Build và kiểm tra production

Windows:

```bat
scripts\build_all.bat
scripts\check_production_build.bat
```

macOS/Linux:

```bash
./scripts/build_all.sh
./scripts/check_production_build.sh
```

Nếu `frontend/dist` bị thiếu, chạy `scripts/build_frontend.bat` hoặc `scripts/build_all.bat`. Script `start_local_prod` cũng tự build khi cần.

## Cấu hình

Mẫu cấu hình nằm tại `packaging/local_app_config.example.json`. App tự phục hồi về cấu hình mặc định nếu file JSON bị hỏng và giữ một file `.bak` để chẩn đoán.

Các đường dẫn gần đây nằm trong `config/recent_paths.json`. Không lưu API key hoặc thông tin đăng nhập trong hai file này.

## Bản Windows EXE

Chạy `packaging\build_windows_exe.ps1`. File EXE dùng launcher hiện tại, phục vụ frontend build và tự mở trình duyệt theo Local App settings.
