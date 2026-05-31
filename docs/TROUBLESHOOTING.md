# Auto Tool Troubleshooting

Tài liệu này liệt kê các lỗi thường gặp khi chạy Auto Tool, kèm nguyên nhân, cách kiểm tra và cách sửa.

## FFmpeg Not Found

Nguyên nhân:

- FFmpeg chưa được cài.
- FFmpeg đã cài nhưng thư mục `bin` chưa có trong `PATH`.
- Bản exe chưa tải FFmpeg thành công.
- `AUTO_TOOL_FFMPEG_DIR` trỏ sai thư mục.

Cách kiểm tra:

```powershell
ffmpeg -version
where ffmpeg
```

Cách sửa:

```powershell
winget install Gyan.FFmpeg
```

Mở terminal mới rồi kiểm tra lại. Nếu vẫn lỗi, set path thủ công:

```powershell
$env:AUTO_TOOL_FFMPEG_DIR="D:\Tools\ffmpeg\bin"
```

Nếu chạy exe, kiểm tra thư mục:

```txt
%LOCALAPPDATA%\AutoTool\tools\ffmpeg
```

## ffprobe Not Found

Nguyên nhân:

- Cài FFmpeg thiếu `ffprobe`.
- `PATH` chỉ có `ffmpeg.exe` nhưng không có `ffprobe.exe`.
- Auto-install FFmpeg bị lỗi.

Cách kiểm tra:

```powershell
ffprobe -version
where ffprobe
```

Cách sửa:

- Cài bản FFmpeg đầy đủ từ Gyan FFmpeg.
- Đảm bảo `ffmpeg.exe` và `ffprobe.exe` nằm cùng thư mục `bin`.
- Set `AUTO_TOOL_FFMPEG_DIR` tới đúng thư mục `bin`.

## Source Folder Not Found

Nguyên nhân:

- Path nhập trên UI sai.
- Path tương đối được resolve từ base folder khác với bạn nghĩ.
- Folder video chưa được copy sang máy đang chạy exe.

Cách kiểm tra:

```powershell
Test-Path "D:\Projects\Auto-Tool\examples\sample_videos\kaw_xmax10"
Get-ChildItem "D:\Projects\Auto-Tool\examples\sample_videos\kaw_xmax10"
```

Cách sửa:

- Nhập absolute path trên UI để tránh nhầm base path.
- Nếu dùng config mẫu, đảm bảo folder `examples/sample_videos/kaw_xmax10` tồn tại.
- Khi đóng gói gửi máy khác, hướng dẫn người dùng chọn đúng folder video local.

## No Valid Videos

Nguyên nhân:

- Folder không có file `.mp4`, `.mov`, `.mkv`, `.webm`.
- Video ngắn dưới 3 giây.
- ffprobe không đọc được file.
- File video bị hỏng hoặc codec không hỗ trợ.

Cách kiểm tra:

```powershell
Get-ChildItem "D:\path\to\videos" -File
ffprobe "D:\path\to\videos\video.mp4"
```

Xem log scan hoặc `project_summary.json`.

Cách sửa:

- Dùng video dài hơn 3 giây.
- Convert video sang MP4 H.264/AAC:

```powershell
ffmpeg -i input.mov -c:v libx264 -c:a aac output.mp4
```

- Kiểm tra lại source folder trong config/UI.

## Render Failed

Nguyên nhân:

- FFmpeg command fail ở bước render visual hoặc render final.
- Không đủ segment để dựng timeline.
- Output folder không ghi được.
- Subtitle/audio/music input lỗi.

Cách kiểm tra:

- Mở `video_XXX_log.json`.
- Xem `steps` để biết fail ở bước nào.
- Xem `errors`.
- Xem `project_summary.json` và `failed_items`.

Cách sửa:

- Nếu fail ở `render_visual`, kiểm tra video nguồn bằng ffprobe.
- Nếu fail ở `generate_voice` hoặc `edge-tts` báo không tạo được audio, kiểm tra internet/voice name rồi chạy lại. Backend sẽ retry Edge TTS rồi tự thử fallback provider như Piper/gTTS/silent.
- Nếu dùng Piper, kiểm tra `PIPER_MODEL_PATH`, `PIPER_CONFIG_PATH` và binary `piper` trong `PATH`.
- Nếu chạy bằng exe, mở lại app để launcher tự cài Piper vào `%LOCALAPPDATA%\AutoTool\tools\piper`.
- Nếu chỉ cần test pipeline, thử `AUTO_TOOL_TTS_PROVIDER=silent` để xác định lỗi TTS.
- Nếu fail ở `render_final`, tắt music/subtitle tạm thời để khoanh vùng.
- Đảm bảo output folder có quyền ghi.

## Subtitle Burn Failed

Nguyên nhân:

- FFmpeg filter `ass` hoặc `subtitles` lỗi.
- Path subtitle có ký tự đặc biệt chưa escape đúng.
- Font/rendering lib của FFmpeg thiếu.
- File `.ass` hoặc `.srt` không hợp lệ.

Cách kiểm tra:

- Xem warning trong `video_XXX_log.json`.
- Kiểm tra file `video_XXX_sub.ass` có tồn tại và có nội dung.
- Kiểm tra step `render_final`.

Cách sửa:

- Chạy lại với path output đơn giản, không dấu/ký tự lạ.
- Cập nhật FFmpeg.
- Nếu chỉ subtitle burn lỗi, renderer có thể fallback video không subtitle và ghi warning.

## Gemini API Key Missing

Nguyên nhân:

- Chưa nhập key trên UI.
- Chưa set `GEMINI_API_KEY` hoặc `GEMINI_API_KEYS`.
- `.env` không nằm đúng vị trí.
- Exe chạy trong môi trường không thấy biến env hiện tại.

Cách kiểm tra:

```powershell
$env:GEMINI_API_KEY
$env:GEMINI_API_KEYS
```

Kiểm tra trong UI phần Gemini API Keys.

Cách sửa:

- Nhập key trên UI, mỗi dòng một key.
- Hoặc tạo file `.env` trong `backend`:

```txt
GEMINI_API_KEY=your_key_here
```

- Khi debug offline, bật fallback:

```powershell
$env:AUTO_TOOL_ALLOW_SCRIPT_FALLBACK="1"
```

## Gemini Response Invalid JSON

Nguyên nhân:

- Model trả thêm markdown hoặc text ngoài JSON.
- Prompt quá dài hoặc thông tin sản phẩm quá rối.
- Model name không đúng.
- API quota/rate limit làm response lỗi.

Cách kiểm tra:

- Mở `video_XXX_log.json`.
- Xem step `generate_script`.
- Kiểm tra `errors` và `warnings`.
- Kiểm tra model trong config `ai.text_model`.

Cách sửa:

- Dùng model đúng.
- Rút gọn description/features.
- Thử API key khác.
- Bật nhiều key để backend rotate khi một key lỗi.
- Tạm bật fallback khi cần render test pipeline.

## Output Folder Permission Denied

Nguyên nhân:

- Output folder nằm trong thư mục cần quyền admin.
- File output cũ đang bị mở bởi player/editor.
- Antivirus khóa file exe hoặc output.
- Disk đầy.

Cách kiểm tra:

```powershell
Test-Path "D:\path\to\outputs"
New-Item -ItemType Directory "D:\path\to\outputs\write_test"
Remove-Item "D:\path\to\outputs\write_test"
```

Cách sửa:

- Chọn output folder trong user directory, ví dụ `D:\AutoToolOutputs`.
- Đóng player đang mở video cũ.
- Kiểm tra dung lượng disk.
- Nếu cần, chạy app với quyền phù hợp.

## Video Duration Mismatch

Nguyên nhân:

- Timeline clip bị cắt ngắn do source không đủ duration.
- Speed variation làm duration thực lệch nhẹ.
- Audio fit hoặc concat có rounding.
- FFmpeg encode thêm/bớt vài frame.

Cách kiểm tra:

```powershell
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 output.mp4
```

Xem QA trong `video_XXX_log.json`:

- Lệch dưới 1.5 giây: pass.
- Lệch dưới 2 giây: warning.
- Lệch trên 2 giây: fail output.

Cách sửa:

- Tăng số lượng và độ dài video nguồn.
- Giảm `speed_variation`.
- Giảm `cut_intensity` nếu segment quá ngắn.
- Kiểm tra source video có duration thật đủ dài.

## Checklist Khi Gặp Lỗi Batch

1. Mở Result page và xem status từng output.
2. Copy error ngắn từ UI.
3. Mở file `video_XXX_log.json` của output lỗi.
4. Xem step đầu tiên có status `failed`.
5. Mở `project_summary.json` để xem `failed_items`.
6. Kiểm tra FFmpeg/ffprobe.
7. Kiểm tra source folder và output folder.
8. Render preview trước khi render full batch lại.
