# App Data Backup, Restore & Cleanup

Tài liệu này mô tả bộ công cụ quản lý dữ liệu local của Auto Tool. Mục tiêu là giúp người dùng sao lưu cấu hình, database, project metadata, subtitle, export pack và log mà không phải thao tác tay trong thư mục app.

## Truy cập trong app

Mở Auto Tool Studio, vào:

```txt
Settings -> Dữ liệu
```

Trang này gồm bốn nhóm:

- Storage Usage: xem dung lượng dữ liệu đang dùng.
- Backup & Restore: tạo file backup `.zip` kèm manifest.
- Restore Backup: inspect và khôi phục backup.
- Cleanup: xem trước rồi dọn cache, temp, log cũ hoặc export cũ.

## API nội bộ

Các endpoint dùng cho UI:

```txt
GET  /api/local-app/storage-usage
POST /api/local-app/backup
GET  /api/local-app/backups
POST /api/local-app/backup/inspect
POST /api/local-app/restore
POST /api/local-app/cleanup/preview
POST /api/local-app/cleanup/run
```

Các endpoint này chỉ dành cho app local, không thiết kế để mở public internet.

## Backup gồm những gì

Mặc định backup gồm:

- Config và settings.
- Database và metadata project.
- Project metadata trong `examples`.
- File subtitle dùng cho review.
- Export pack.

Mặc định không backup:

- Video output cuối cùng.
- Source video gốc.
- Music folder ngoài project.
- `.env`, API key, credential, token.
- `.venv`, `node_modules`, cache build.

Người dùng có thể bật thêm `Final output videos`, nhưng backup có thể rất nặng.

## Manifest

Mỗi backup có:

```txt
backups/<backup_name>.zip
backups/<backup_name>.manifest.json
```

Trong file `.zip` cũng có `backup_manifest.json`. Manifest giúp inspect backup trước khi restore, gồm version app, thời điểm tạo, danh sách category và danh sách file.

## Restore an toàn

Luồng restore khuyến nghị:

1. Chọn file backup `.zip`.
2. Bấm Inspect Backup.
3. Kiểm tra category và số lượng file.
4. Giữ bật `Create backup before restore`.
5. Chỉ bật `Overwrite existing files` khi thật sự cần.
6. Tick xác nhận rồi chạy Restore.

Restore có các lớp bảo vệ:

- Chặn zip-slip path traversal.
- Không restore file nhạy cảm.
- Không ghi đè file hiện có nếu người dùng chưa bật overwrite.
- Tạo pre-restore backup trước khi ghi dữ liệu nếu tùy chọn đang bật.

## Cleanup an toàn

Cleanup luôn có hai bước:

1. Preview Cleanup.
2. Run Cleanup sau khi người dùng xác nhận.

Những target hiện có:

- Launcher logs cũ.
- Debug logs cũ.
- Temp files.
- Cache files.
- Preview frames.
- Failed partial renders.
- Old export packs.

Cleanup không được xóa:

- Source videos.
- Music folder.
- Database.
- Config.
- API key, credential, token.
- Video final từ render lỗi một phần.

## Khi nào nên backup

Nên tạo backup trước khi:

- Update app hoặc build exe mới.
- Chạy cleanup lớn.
- Restore từ backup cũ.
- Di chuyển app sang máy khác.
- Render batch lớn có nhiều project metadata quan trọng.

## Khi nào nên cleanup

Nên cleanup khi:

- App data phình to do log, cache, temp.
- Có nhiều preview frames hoặc debug logs.
- Muốn dọn export pack cũ đã không dùng nữa.

Không nên cleanup khi đang render hoặc đang mở file output trong trình phát video.

## Kiểm tra nhanh bằng API

```bash
curl http://127.0.0.1:8000/api/local-app/storage-usage
curl http://127.0.0.1:8000/api/local-app/backups
```

Tạo backup:

```bash
curl -X POST http://127.0.0.1:8000/api/local-app/backup ^
  -H "Content-Type: application/json" ^
  -d "{\"include_config\":true,\"include_database\":true,\"include_projects\":true,\"include_outputs\":false,\"include_exports\":true,\"include_subtitles\":true,\"include_logs\":false}"
```

