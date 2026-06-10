# Douyin Reup E2E QA Checklist

Use this checklist with real local Douyin videos in `sample_videos/douyin_reup_test_pack/`.

```txt
[ ] Scan folder nhận đúng video
[ ] Video lỗi không làm crash batch
[ ] Sidecar SRT được ưu tiên nếu có
[ ] Không có SRT thì ASR chạy
[ ] ASR lỗi thì video failed, batch vẫn tiếp tục
[ ] Dịch SRT giữ nguyên timestamp
[ ] Subtitle Review Document được tạo
[ ] UI mở được từng document
[ ] Sửa subtitle và save được
[ ] Approve tạo corrected SRT/ASS
[ ] Render approved video thành công
[ ] Overlay/subtitle nằm đúng vùng dưới
[ ] BGM được mix vào video
[ ] Audio gốc không bị mất nếu original_audio_volume > 0
[ ] Output có video, SRT, ASS, log, summary
```

Common edge cases:

```txt
[ ] Folder không tồn tại trả message rõ
[ ] Folder rỗng trả warning rõ
[ ] Video không có audio không crash
[ ] Video audio quá nhỏ không crash batch
[ ] Video quá ngắn có warning
[ ] Video dài trên 30s vẫn có summary/performance
[ ] File tên tiếng Việt / tiếng Trung / ký tự đặc biệt xử lý được
[ ] SRT sai format fail ở translation/timing với message rõ
[ ] Gemini dịch lỗi không in raw traceback
[ ] ASR dependency thiếu gợi ý cài faster-whisper hoặc tắt ASR
[ ] BGM folder rỗng có warning, không fail batch
[ ] BGM file lỗi fallback giữ audio gốc
[ ] Output folder không có quyền ghi trả message dễ hiểu
[ ] Subtitle quá dài có warning trong review
[ ] Subtitle vượt duration video có warning trong review
[ ] Render FFmpeg lỗi có failed_step=render
```
