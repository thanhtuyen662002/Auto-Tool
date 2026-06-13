# Data Management QA Checklist

Dùng checklist này trước khi release build có tính năng backup, restore và cleanup.

## Storage Usage

- [ ] Mở `Settings -> Dữ liệu`.
- [ ] Storage Usage tải được tổng dung lượng.
- [ ] Các category chính hiển thị: config, database, outputs, logs, cache, temp, backups.
- [ ] Nút Refresh không làm crash UI.
- [ ] Nếu backend tắt, UI hiển thị lỗi rõ.

## Backup

- [ ] Tạo backup mặc định thành công.
- [ ] File `.zip` được tạo trong `backups/`.
- [ ] File `.manifest.json` được tạo cạnh file `.zip`.
- [ ] Trong zip có `backup_manifest.json`.
- [ ] Backup không chứa `.env`, API key, credential, token.
- [ ] Backup không chứa `.venv`, `node_modules`, `__pycache__`.
- [ ] Khi không bật output videos, backup không kéo theo `examples/outputs`.
- [ ] Khi bật output videos, output folder được đưa vào backup.
- [ ] API `GET /api/local-app/backups` trả danh sách backup mới nhất.

## Inspect Backup

- [ ] Chọn file `.zip` hợp lệ và inspect thành công.
- [ ] Inspect hiển thị category, số file, dung lượng.
- [ ] File zip hỏng trả lỗi rõ.
- [ ] Zip có path traversal bị chặn.

## Restore

- [ ] Restore mặc định tạo pre-restore backup.
- [ ] Restore không overwrite file hiện có khi `overwrite_existing=false`.
- [ ] Restore có thể overwrite khi người dùng bật tùy chọn.
- [ ] Restore bỏ qua file nhạy cảm.
- [ ] Restore báo danh sách category đã restore.
- [ ] UI bắt buộc tick xác nhận trước khi restore.

## Cleanup Preview

- [ ] Preview chạy được khi chọn target mặc định.
- [ ] Preview trả tổng số file và dung lượng có thể xóa.
- [ ] Preview không xóa file thật.
- [ ] Target `failed_partial_renders` không xóa video final.
- [ ] Target `old_exports` chỉ liệt kê export pack cũ.

## Cleanup Run

- [ ] Run bị chặn nếu chưa confirm.
- [ ] Sau khi confirm, chỉ xóa các file trong preview.
- [ ] Config, database, source videos, music folder không bị xóa.
- [ ] Kết quả trả `deleted_file_count` và `deleted_size_bytes`.
- [ ] Lỗi permission được ghi rõ, batch cleanup vẫn tiếp tục file khác nếu có thể.

## API Regression

- [ ] `GET /api/local-app/storage-usage` trả 200.
- [ ] `POST /api/local-app/backup` trả 200 với request hợp lệ.
- [ ] `GET /api/local-app/backups` trả 200.
- [ ] `POST /api/local-app/backup/inspect` trả 200 với backup hợp lệ.
- [ ] `POST /api/local-app/restore` trả lỗi rõ khi thiếu `backup_path`.
- [ ] `POST /api/local-app/cleanup/preview` không xóa dữ liệu.
- [ ] `POST /api/local-app/cleanup/run` không xóa nếu `confirm_delete=false`.

## Build

- [ ] `py -m pytest backend/tests` pass.
- [ ] `npm run build` trong `frontend/` pass.
- [ ] Launcher one-click vẫn mở app.
- [ ] EXE build vẫn phục vụ frontend và API trên cùng port.

