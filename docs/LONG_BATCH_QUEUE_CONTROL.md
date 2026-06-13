# Long Batch Queue Control

Tính năng này giúp Auto Tool Studio chạy batch dài ổn định hơn, đặc biệt với Douyin Reup, Silent Mode và render sản phẩm nhiều output.

## Mục tiêu

- Theo dõi từng video trong batch bằng `queue_state.json`.
- Tạm dừng sau video hiện tại thay vì kill tiến trình giữa chừng.
- Hủy batch an toàn, giữ lại output đã render xong.
- Retry video lỗi hoặc item được chọn.
- Ưu tiên, đưa lên đầu hoặc xuống cuối hàng đợi trước khi video đó bắt đầu.
- Cảnh báo tài nguyên trước khi chạy item tiếp theo.

## File trạng thái

Auto Tool ghi trạng thái queue ở hai nơi:

```txt
app_data/data/queue_control/<job_id>/
  queue_state.json
  queue_items.json
  queue_events.log

output_folder/
  queue_state.json
  queue_items.json
  queue_events.log
```

File trong app data là nguồn chính. File trong output folder giúp debug nhanh khi gửi log hoặc kiểm tra thủ công.

## API

```txt
GET  /api/queue-control/jobs/{job_id}
POST /api/queue-control/jobs/{job_id}/pause
POST /api/queue-control/jobs/{job_id}/resume
POST /api/queue-control/jobs/{job_id}/cancel
POST /api/queue-control/jobs/{job_id}/retry-failed
POST /api/queue-control/jobs/{job_id}/retry-selected
POST /api/queue-control/jobs/{job_id}/skip-selected
POST /api/queue-control/jobs/{job_id}/prioritize-selected
POST /api/queue-control/jobs/{job_id}/move-to-top
POST /api/queue-control/jobs/{job_id}/move-to-bottom
GET  /api/queue-control/jobs/{job_id}/resource-status
```

Các endpoint thao tác item nhận body:

```json
{
  "item_ids": ["job-id:item:001", "job-id:item:002"]
}
```

## Cơ chế pause/cancel

Auto Tool không dừng FFmpeg, ASR hoặc OCR giữa một video đang xử lý. Khi người dùng bấm tạm dừng hoặc hủy:

1. API ghi cờ vào `queue_state.json`.
2. Worker hoàn tất video hiện tại.
3. Trước video kế tiếp, worker đọc lại queue state.
4. Nếu pause, job chuyển sang `paused`.
5. Nếu cancel, job chuyển sang `cancelled`.

Cách này chậm hơn việc kill process ngay lập tức, nhưng tránh file hỏng và giữ log/output nhất quán.

## Reorder và priority

Worker luôn đọc item kế tiếp từ queue state trước khi chạy video mới. Item được sort theo:

1. `priority`: `high`, `normal`, `low`
2. `order_index`

Vì vậy thao tác `prioritize-selected`, `move-to-top`, `move-to-bottom` có hiệu lực với các item chưa chạy. Item đang chạy hoặc đã xong không bị reorder.

## Retry

- `retry-failed`: đưa item lỗi về trạng thái `queued`, sau đó dùng Job Recovery để tạo job resume/retry khi phù hợp.
- `retry-selected`: reset các item đang `failed`, `paused`, `skipped`, `cancelled` về `queued`.

Với Douyin failed outputs, retry job dùng lại pipeline retry Douyin hiện có để tận dụng cache SRT/source/translation khi có.

## Resource Guard

Resource guard kiểm tra trước item kế tiếp:

- Dung lượng ổ đĩa còn trống.
- CPU/RAM nếu có `psutil`.

Nếu dung lượng ổ đĩa thấp hơn `min_free_disk_gb`, job tạm dừng trước khi bắt đầu item mới. Cảnh báo CPU/RAM chỉ được ghi log, không tự fail batch.

## Frontend

Trang `RenderQueuePage` có:

- Tiến trình job tổng.
- Panel pause/resume/cancel/retry/skip/reorder.
- Danh sách video trong queue.
- Log polling mỗi 2 giây.

Người dùng có thể chọn các item chưa chạy/xử lý lỗi để thao tác.

## Giới hạn hiện tại

- Chưa chạy song song nhiều video. `max_concurrent_videos` được giữ an toàn ở 1 nếu pipeline chưa bật parallel rõ ràng.
- Resume tạo job mới khi job đã dừng, không tiếp tục thread cũ đã kết thúc.
- Reorder chỉ áp dụng cho item chưa chạy.
- Pause/cancel không ngắt bước FFmpeg/ASR/OCR đang chạy dở.
