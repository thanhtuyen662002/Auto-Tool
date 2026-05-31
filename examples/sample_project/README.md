# Sample Project

Project mẫu này dùng để chạy thử pipeline Auto Tool end-to-end bằng CLI hoặc UI.

## Chuẩn Bị Video

Project đã có sẵn vài video dummy ngắn để test kỹ thuật. Khi test sản phẩm thật, thay bằng 3-5 file video `.mp4`, `.mov`, `.mkv` hoặc `.webm` trong thư mục:

```txt
examples/sample_project/sample_videos/sample_product/
```

Video nên dài hơn 4 giây để scanner và segmenter có đủ dữ liệu. Nếu dùng video quá ngắn, backend sẽ bỏ qua và báo `No valid input videos found`.

## Chạy CLI

```powershell
cd backend
py -m app.main --config ../examples/sample_project/product_config.example.json
```

Output mặc định được tạo trong:

```txt
examples/sample_project/outputs/
```

Mỗi lần render full batch sẽ có `project_summary.json`, `segment_scoring_report.json`, `script_variants.json` và log riêng cho từng video.

## Ghi Chú TTS

Mặc định Auto Tool dùng `edge_tts` để tạo voice tiếng Việt, sau đó fallback qua Piper, gTTS và silent nếu provider trước lỗi. Nếu chỉ muốn test nhanh pipeline mà không cần voice thật:

Nếu chạy bằng `AutoTool.exe`, app tự tải và setup Piper/voice tiếng Việt trong lần mở đầu tiên. Người dùng không cần tự set biến môi trường cho Piper.

```powershell
$env:AUTO_TOOL_TTS_PROVIDER="silent"
```

Khi render thật, nên dùng:

```powershell
$env:AUTO_TOOL_TTS_PROVIDER="edge_tts"
$env:AUTO_TOOL_TTS_FALLBACK_PROVIDER="piper"
$env:AUTO_TOOL_TTS_VOICE="vi-VN-HoaiMyNeural"
```
