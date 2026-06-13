# Long Batch Queue Control QA Checklist

## Chuẩn bị

- Có ít nhất 5 video nguồn hợp lệ.
- Backend chạy bằng `uvicorn app.main:app --reload --port 8000`.
- Frontend chạy bằng `npm run dev`.
- Mở trang hàng đợi sau khi bắt đầu render.

## Backend API

- `GET /api/queue-control/jobs/{job_id}` trả `queue_state` có đúng `total_items`.
- `POST /pause` chuyển job sang `pausing`, sau video hiện tại thành `paused`.
- `POST /cancel` chuyển job sang `cancel_requested`, sau video hiện tại thành `cancelled`.
- `POST /skip-selected` chỉ skip item chưa chạy hoặc chưa xong.
- `POST /prioritize-selected` đổi priority item chưa chạy sang `high`.
- `POST /move-to-top` đổi thứ tự item chưa chạy.
- `POST /move-to-bottom` đổi thứ tự item chưa chạy.
- `POST /retry-failed` reset item lỗi và tạo resume/retry job khi có dữ liệu phù hợp.
- `GET /resource-status` trả dung lượng ổ đĩa và warning nếu thiếu.

## Product Render

- Bắt đầu batch 3 output.
- Kiểm tra `queue_state.json` xuất hiện trong app data và output folder.
- Bấm pause khi video 1 đang chạy.
- Kỳ vọng video 1 hoàn tất, video 2 chưa bắt đầu, job thành `paused`.
- Bấm resume.
- Kỳ vọng app tạo resume job hoặc chuyển trạng thái tiếp tục rõ ràng.
- Bấm cancel trước video kế tiếp.
- Kỳ vọng output đã xong còn nguyên, item chưa chạy thành `cancelled`.

## Douyin Reup

- Chạy batch 5 video bằng preset an toàn.
- Bấm move-to-bottom cho video 2 trước khi nó chạy.
- Kỳ vọng video 2 không còn là item kế tiếp.
- Bấm prioritize cho một item chờ.
- Kỳ vọng item đó chạy trước các item normal còn lại.
- Bấm pause trong lúc ASR/OCR/FFmpeg đang chạy.
- Kỳ vọng job không bị kill giữa bước, chỉ dừng trước video kế tiếp.

## Resource Guard

- Tạo queue state với `min_free_disk_gb` rất cao trong test.
- Kỳ vọng resource warning xuất hiện.
- Kỳ vọng job pause trước item mới khi warning là dung lượng ổ đĩa thấp.

## Frontend

- RenderQueuePage hiển thị tiến trình tổng.
- Panel queue hiển thị đúng trạng thái running/paused/cancelled.
- Checkbox không chọn được item đang running hoặc completed.
- Chọn item lỗi và bấm Retry đã chọn không crash UI.
- Bấm Retry lỗi khi không có item lỗi thì nút disabled.
- Log hiển thị tiếng Việt có dấu.
- Polling cập nhật item status trong vòng 2 giây.

## File output cần kiểm tra

```txt
output_folder/
  queue_state.json
  queue_items.json
  queue_events.log
```

Mỗi file phải đọc được bằng UTF-8 và không chứa JSON hỏng.

## Regression

- CLI render cũ vẫn chạy.
- API render cũ vẫn trả `{ job_id, status: "queued" }`.
- Job một video vẫn render xong bình thường.
- Batch có một video lỗi không crash toàn bộ worker.
- Frontend build không lỗi TypeScript.
