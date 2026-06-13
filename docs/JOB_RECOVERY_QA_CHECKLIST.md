# Job Recovery QA Checklist

## Backend

- [ ] Job checkpoint được tạo khi job bắt đầu chạy.
- [ ] `job_checkpoint.json` có `job_id`, `mode`, `status`, `last_checkpoint_at`.
- [ ] `settings_snapshot.json` được tạo.
- [ ] Step checkpoint ghi được trạng thái started/completed/failed.
- [ ] Checkpoint JSON hỏng không làm backend crash.
- [ ] Backend startup đánh dấu job `running` cũ thành `recoverable` hoặc `interrupted`.
- [ ] `/api/health` trả `recoverable_jobs_count`.
- [ ] `/api/job-recovery/candidates` trả danh sách job có thể khôi phục.
- [ ] `/api/job-recovery/jobs/{job_id}` trả checkpoint, video checkpoints và reconciliation.
- [ ] `/api/job-recovery/jobs/{job_id}/reconcile` kiểm tra output đã tồn tại.
- [ ] `/api/job-recovery/jobs/{job_id}/resume` tạo `resume_manifest.json`.
- [ ] Resume không ghi đè output đã tồn tại.
- [ ] Job lock ngăn resume trùng.
- [ ] Cleanup lock hoạt động.
- [ ] Mark cancelled đổi job sang `cancelled`.

## Frontend

- [ ] Sidebar có mục Khôi phục.
- [ ] Banner recovery hiện khi `recoverable_jobs_count > 0`.
- [ ] Recovery Center load được danh sách job.
- [ ] Job card hiển thị project name, mode, progress, failed/interrupted count.
- [ ] Resume modal có các mode resume.
- [ ] Tùy chọn “Bỏ qua video đã xong” bật mặc định.
- [ ] Tùy chọn “Không ghi đè output cũ” bật mặc định.
- [ ] Reconcile hiển thị thông báo rõ.
- [ ] Open partial results điều hướng sang Results.
- [ ] Mark cancelled có phản hồi rõ.
- [ ] Backend offline không làm UI crash.

## Manual crash simulation

1. Chạy batch nhiều video.
2. Tắt backend khi đang render.
3. Mở lại app.
4. Kiểm tra banner recovery xuất hiện.
5. Mở Recovery Center.
6. Chạy Reconcile.
7. Resume job.
8. Kiểm tra video đã render không bị ghi đè.
9. Kiểm tra job mới có `resume_manifest.json`.

## Release Gate

- [ ] `py -m pytest backend/tests` pass.
- [ ] `npm run build` trong `frontend/` pass.
- [ ] One-click launcher vẫn mở app.
- [ ] Existing Douyin Reup flow vẫn chạy.
- [ ] Existing Silent Mode flow vẫn chạy.
- [ ] Backup/Restore/Cleanup Tools vẫn chạy.

