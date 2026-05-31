# Auto Tool Release QA Checklist — v0.1.0-rc1

## Environment

- [ ] Python >= 3.11 (`py --version`)
- [ ] Node >= 18 (`node --version`)
- [ ] FFmpeg installed (`ffmpeg -version`)
- [ ] ffprobe installed (`ffprobe -version`)
- [ ] Backend `.env` exists (`backend/.env`)
- [ ] Frontend `.env.example` đã được copy thành `.env` nếu cần
- [ ] System check page works (`/api/health` trả `{ "status": "ok", "version": "0.1.0-rc1" }`)

## Backend

- [ ] `/api/health` trả `status: ok` và `version: 0.1.0-rc1`
- [ ] `/api/system/check` (nếu có) hoạt động
- [ ] Create project (`POST /api/projects`) hoạt động
- [ ] Scan videos (`POST /api/projects/{id}/scan`) hoạt động
- [ ] Segment scoring (`POST /api/projects/{id}/analyze-segments`) hoạt động
- [ ] Render preview (`POST /api/projects/{id}/render` với `preview_only: true`) hoạt động
- [ ] Render full batch (`POST /api/projects/{id}/render`) hoạt động
- [ ] Rerender selected (`POST /api/projects/{id}/rerender`) hoạt động
- [ ] Content export (`POST /api/projects/{id}/content/export`) hoạt động
- [ ] Job status polling (`GET /api/jobs/{id}`) hoạt động

## Frontend

- [ ] CreateProjectPage hiển thị form tạo dự án
- [ ] RenderSettingsPage tải được cấu hình
- [ ] Simple Mode hoạt động (số lượng video, độ dài, style, giọng đọc)
- [ ] Advanced Mode hoạt động (effect sliders, TTS provider, timeline template)
- [ ] Script Editor Form hiển thị và có thể chỉnh sửa
- [ ] RenderQueuePage hiển thị tiến trình render realtime
- [ ] ResultPage hiển thị danh sách kết quả
- [ ] OutputReviewPage tải và hiển thị điểm chất lượng
- [ ] ContentManagerPage hiển thị caption và cho phép export
- [ ] Không có trang nào bị trắng màn hình khi lỗi (ErrorBoundary đã được bọc)
- [ ] Footer hiển thị version `Auto Tool v0.1.0-rc1`

## Output Files

- [ ] `{name}.mp4` — video cuối cùng tồn tại
- [ ] `{name}_script.json` — file kịch bản tồn tại
- [ ] `{name}_sub.srt` — file phụ đề SRT tồn tại
- [ ] `{name}_sub.ass` — file phụ đề ASS tồn tại
- [ ] `{name}_voice.mp3` (hoặc .wav) — file giọng đọc tồn tại
- [ ] `{name}_timeline.json` — file timeline tồn tại
- [ ] `{name}_log.json` — file log tồn tại và có `performance` dict
- [ ] `project_summary.json` — tổng kết dự án tồn tại và có `performance_summary`
- [ ] `segment_scoring_report.json` — báo cáo chấm điểm tồn tại
- [ ] `script_variants.json` — file biến thể kịch bản tồn tại
- [ ] Export files (json/csv/txt/md) tồn tại sau khi export

## Performance Metrics (trong `{name}_log.json`)

- [ ] `performance.render_visual_seconds` có giá trị
- [ ] `performance.script_seconds` có giá trị
- [ ] `performance.tts_seconds` có giá trị
- [ ] `performance.subtitle_seconds` có giá trị
- [ ] `performance.render_final_seconds` có giá trị
- [ ] `performance.total_seconds` có giá trị

## Performance Summary (trong `project_summary.json`)

- [ ] `performance_summary.total_runtime_seconds` có giá trị
- [ ] `performance_summary.average_time_per_video` có giá trị
- [ ] `performance_summary.slowest_step` có giá trị
- [ ] `performance_summary.slowest_output_index` có giá trị

## Smoke Test

- [ ] Smoke test chạy được:
  ```bash
  cd backend
  py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json
  ```
- [ ] Output cuối là JSON `{ "status": "success", "steps": {...} }`
- [ ] Tất cả steps trong JSON là `"ok"` (không có `"fail"`)

## Automated Tests

- [ ] Backend tests chạy được:
  ```bash
  cd backend
  py -m pytest -v
  ```
- [ ] Không có test nào fail
- [ ] Tests không phụ thuộc internet (edge TTS đã được mock)

## Frontend Build

- [ ] Frontend build thành công:
  ```bash
  cd frontend
  npm run build
  ```
- [ ] Không có TypeScript error
- [ ] Không có warning nghiêm trọng

## End-To-End Flow

- [ ] Create Project → chọn thư mục có video
- [ ] System Check → kiểm tra FFmpeg, Python
- [ ] Scan Videos → tìm thấy video hợp lệ
- [ ] Segment Scoring → chấm điểm cảnh quay
- [ ] Render Preview → tạo 1 video thử
- [ ] Edit Script → chỉnh sửa kịch bản trong form
- [ ] Save Script → lưu kịch bản
- [ ] Render Full Batch → render toàn bộ video
- [ ] Review Output Quality → kiểm tra điểm chất lượng
- [ ] Rerender Bad/Failed Videos → render lại video kém
- [ ] Manage Captions → chỉnh sửa caption, hashtag
- [ ] Export Content → tải xuống file JSON/CSV/TXT/MD

## Error Handling

- [ ] Source folder không tồn tại → hiển thị thông báo rõ ràng (không phải raw traceback)
- [ ] Output folder không có quyền ghi → hiển thị thông báo rõ ràng
- [ ] Video input quá ngắn → bị bỏ qua với warning
- [ ] Edge-TTS lỗi mạng → hiển thị thông báo yêu cầu kiểm tra kết nối
- [ ] Không đủ segment dùng được → hiển thị thông báo rõ ràng
- [ ] Frontend crash → ErrorBoundary hiển thị message thân thiện

---

*Cập nhật lần cuối: 2026-05-31 | Phiên bản: 0.1.0-rc1*
