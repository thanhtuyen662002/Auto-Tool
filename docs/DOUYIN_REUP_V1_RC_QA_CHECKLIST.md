# Douyin Reup v1.0 RC QA Checklist

## Setup

- [ ] Backend chạy được
- [ ] Frontend chạy được
- [ ] FFmpeg/ffprobe hoạt động
- [ ] Gemini/API translation config hoạt động hoặc mock mode hoạt động
- [ ] ASR provider hoạt động hoặc mock mode hoạt động
- [ ] OCR provider hoạt động hoặc mock mode hoạt động
- [ ] BGM folder đọc được

## Scan

- [ ] Folder tồn tại scan được
- [ ] Folder rỗng có warning rõ
- [ ] Video lỗi không crash batch
- [ ] File tên tiếng Việt/Trung/ký tự đặc biệt xử lý được
- [ ] Metadata duration/resolution/fps đúng

## Subtitle Source

- [ ] Sidecar SRT được ưu tiên
- [ ] Embedded subtitle được extract nếu có
- [ ] Không có SRT thì ASR chạy
- [ ] ASR fail thì OCR fallback nếu preset cho phép
- [ ] OCR tạo source_zh_ocr.srt nếu có chữ dính màn hình
- [ ] Không tìm được source subtitle thì video failed rõ lý do

## Translation

- [ ] Dịch Trung -> Việt giữ timestamp
- [ ] Dịch không đổi số lượng block nếu có thể
- [ ] Dịch không thêm ý mới
- [ ] Giữ tên riêng/thương hiệu/số liệu/đơn vị
- [ ] Translation fail không crash batch

## Subtitle Review

- [ ] Review document được tạo
- [ ] UI mở được document
- [ ] Video preview seek đúng dòng subtitle
- [ ] Sửa dòng subtitle lưu được
- [ ] Approve tạo corrected SRT
- [ ] Approve tạo corrected ASS

## Subtitle Quality

- [ ] Quality score được tạo
- [ ] Dòng quá dài được flag
- [ ] Dòng còn tiếng Trung được flag
- [ ] OCR confidence thấp được flag
- [ ] Next flagged line hoạt động
- [ ] Approval guard cảnh báo khi còn critical

## Rewrite

- [ ] Suggest rewrite cho một dòng hoạt động
- [ ] Apply suggestion cập nhật edited_text
- [ ] Quality score refresh sau khi apply
- [ ] Bulk rewrite tạo suggestion cho flagged lines
- [ ] Không auto apply suggestion có warning nghiêm trọng

## Render

- [ ] Render video bằng corrected subtitle
- [ ] Overlay/subtitle style đúng
- [ ] Subtitle nằm vùng dưới
- [ ] BGM được mix
- [ ] Original audio không mất nếu keep_original_audio=true
- [ ] Render lỗi có failed_step rõ

## Final QA

- [ ] Final QA chạy sau render
- [ ] Video đọc được
- [ ] Duration/resolution/fps được check
- [ ] Audio quá nhỏ/quá to có warning
- [ ] Subtitle/overlay missing có warning
- [ ] QA score hiển thị trên Results Page

## Export Pack

- [ ] Export Pack tạo đủ folder
- [ ] videos/ có video final
- [ ] subtitles/ có source/corrected/ass
- [ ] captions/ có txt/csv
- [ ] logs/ có log JSON
- [ ] qa/ có QA report
- [ ] posting_checklist.md được tạo
- [ ] export_manifest.json đúng
