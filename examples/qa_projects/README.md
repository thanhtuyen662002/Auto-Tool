# QA Sample Projects

Thư mục này chứa các cấu hình mẫu để kiểm tra end-to-end pipeline của Auto Tool.

## Cấu hình có sẵn

| File | Sản phẩm | output_count | Mục đích |
|------|----------|-------------|---------|
| `projector_config.json` | Máy chiếu | 3 | Kiểm tra flow cơ bản với sản phẩm điện tử |
| `fan_config.json` | Quạt | 3 | Kiểm tra sản phẩm gia dụng |
| `jacket_config.json` | Áo khoác | 3 | Kiểm tra sản phẩm thời trang |

Tất cả config dùng `output_count: 3` — đủ để test pipeline mà không mất quá nhiều thời gian render.

---

## Cách sử dụng

### 1. Chuẩn bị video mẫu

Tạo các thư mục và bỏ video thật vào:

```
examples/sample_videos/
  projector/        ← video máy chiếu (tối thiểu 3 file .mp4, mỗi file >= 10 giây)
  fan/              ← video quạt
  jacket/           ← video áo khoác
```

> **Lưu ý:** Video cần dài tối thiểu **3 giây**. Video quá ngắn sẽ bị bỏ qua tự động.  
> Định dạng hỗ trợ: `.mp4`, `.mov`, `.mkv`, `.webm`

### 2. Cập nhật đường dẫn trong config

Mở file config (ví dụ `projector_config.json`) và cập nhật:

```json
{
  "source_folder": "C:/path/to/your/projector_videos",
  "output_folder": "C:/path/to/your/outputs/projector"
}
```

Hoặc dùng đường dẫn tương đối từ thư mục backend:
```json
{
  "source_folder": "../examples/sample_videos/projector",
  "output_folder": "../examples/outputs/projector"
}
```

### 3. Thêm API keys

Chỉnh sửa `backend/.env` hoặc thêm vào phần `ai` trong config:

```json
{
  "ai": {
    "gemini_api_keys": ["your-gemini-api-key-here"]
  }
}
```

> Nếu không có API key, script sẽ được tạo tự động theo template mặc định.

---

## Chạy Smoke Test (không cần video thật)

```bash
cd backend
py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json
```

Smoke test mặc định chạy **mock mode** — không cần video thật, không cần mạng. Tốt để kiểm tra môi trường cài đặt.

```bash
# Để test với video thật và mạng thật:
py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json --no-mock
```

Output mẫu khi thành công:

```json
{
  "status": "success",
  "steps": {
    "load_config": "ok",
    "check_env": "ok",
    "scan": "ok",
    "segment": "ok",
    "segment_scoring": "ok",
    "timeline": "ok",
    "script": "ok",
    "tts": "ok",
    "subtitle": "ok",
    "render_preview": "ok",
    "qa": "ok"
  },
  "preview_path": "..."
}
```

---

## Chạy qua giao diện Web

1. Khởi động backend: `cd backend && py -m app.main`
2. Khởi động frontend: `cd frontend && npm run dev`
3. Mở trình duyệt: `http://localhost:5173`
4. Tạo dự án mới và chọn thư mục video từ `sample_videos/`
