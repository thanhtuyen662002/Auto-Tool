# Crash Recovery & Job Resume

Tính năng này giúp Auto Tool Studio phát hiện và xử lý các job bị gián đoạn khi app bị tắt giữa batch.

## Khi nào dùng?

Dùng Recovery Center khi:

- Backend bị tắt trong lúc render.
- Máy sleep, mất điện hoặc Windows restart.
- Browser đóng trong lúc job vẫn đang chạy.
- Render dừng ở giữa batch và job không hoàn tất.
- Cần mở lại kết quả tạm thời trước khi resume.

## App khôi phục như thế nào?

Auto Tool ghi checkpoint theo job:

```txt
app_data/data/job_recovery/<job_id>/
  job_checkpoint.json
  video_checkpoints.json
  settings_snapshot.json
  resume_manifest.json
  resume_log.json
```

Khi backend start lại:

1. App kiểm tra các job còn trạng thái `queued`, `running` hoặc `processing`.
2. Các job đó được đánh dấu `interrupted` hoặc `recoverable`.
3. App không tự resume.
4. Người dùng mở Recovery Center để chọn hành động.

## Recovery Center

Mở:

```txt
/recovery
```

Hoặc vào `Settings -> Dữ liệu -> Job Recovery`.

Các hành động chính:

- Resume safely: tạo job resume mới.
- Reconcile: kiểm tra output đã tồn tại và cập nhật trạng thái đọc được.
- Mở kết quả tạm thời: xem video đã render được.
- Cleanup lock: gỡ lock nếu chắc chắn job resume cũ không còn chạy.
- Đánh dấu đã hủy: đổi job sang `cancelled`.

## Các lựa chọn resume

- Reconcile then continue: mặc định, kiểm tra output đã có, bỏ qua phần đã xong và xử lý phần còn lại.
- Retry interrupted only: chỉ retry mục đang dở.
- Retry failed only: chỉ retry mục lỗi.
- Continue pending only: chỉ xử lý mục chưa bắt đầu.

Mặc định:

```txt
[x] Bỏ qua video đã xong
[x] Không ghi đè output cũ
```

## Dữ liệu không bị ghi đè

Khi `do_not_overwrite_existing_outputs=true`, app không ghi đè output đã tồn tại và đọc được. Resume tạo job mới và manifest mới để giữ đường lui.

Với Douyin failed outputs, app ưu tiên dùng retry pipeline sẵn có. Với render sản phẩm thông thường, resume tạo output folder timestamp mới, tránh ghi đè folder cũ.

## Job lock

Mỗi resume tạo lock:

```txt
app_data/data/job_locks/<job_id>.lock
```

Lock tránh việc người dùng bấm resume nhiều lần cho cùng một job. Nếu app bị tắt khi đang resume, lock cũ có thể được cleanup trong Recovery Center.

## Lưu ý

- App không tự resume khi mở lại.
- Checkpoint JSON hỏng sẽ được đổi tên sang `.corrupt.<timestamp>` và không làm app crash.
- Không xóa partial output trong hệ thống recovery.
- Resume luôn tạo `resume_manifest.json` và `resume_log.json`.

