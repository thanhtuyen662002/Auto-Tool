# Silent Mode v1 RC QA Checklist

## Setup

- [ ] Backend chạy được
- [ ] Frontend chạy được
- [ ] FFmpeg/ffprobe hoạt động
- [ ] OCR provider hoạt động hoặc `--mock-ocr` hoạt động
- [ ] TTS provider hoạt động hoặc `--mock-tts` hoạt động
- [ ] BGM folder đọc được
- [ ] Visual style presets load được

## Silent Detection

- [ ] Video không audio được detect là silent
- [ ] Video chỉ có nhạc được detect là silent
- [ ] Video có tiếng thao tác nhưng không thoại vẫn dùng Silent Mode
- [ ] Video có lời thoại rõ không bị ép silent nếu không chọn silent preset
- [ ] User có thể ép dùng silent preset thủ công

## Visual Segmentation

- [ ] Visual segments được tạo
- [ ] Segment duration hợp lý
- [ ] Representative frame được tạo
- [ ] Segment quá tối hoặc mờ có warning/tag chất lượng
- [ ] Video ngắn vẫn tạo được segment
- [ ] Video ngang hoặc vuông không làm crash

## Visual Tagging

- [ ] Keyword folder/filename map đúng industry
- [ ] OCR text map đúng tag nếu có
- [ ] Segment type map đúng action tag
- [ ] Recommended industry được tạo
- [ ] User sửa tag được
- [ ] Regenerate caption sau khi sửa tag hoạt động mà không analyze lại video

## Caption Generation

- [ ] OCR translated caption được ưu tiên nếu OCR tốt
- [ ] Không có OCR thì dùng template caption
- [ ] Caption đúng industry đã chọn
- [ ] Caption không quá dài
- [ ] Caption không lặp quá nhiều trong cùng video
- [ ] CTA xuất hiện ở segment cuối
- [ ] Product context giúp caption cụ thể hơn
- [ ] Không có product context vẫn tạo caption chung hợp lý

## Caption Review

- [ ] SubtitleReviewDocument được tạo
- [ ] Source hiển thị đúng OCR, visual generated hoặc template
- [ ] User sửa caption được
- [ ] User approve được
- [ ] Corrected SRT được tạo
- [ ] Corrected ASS được tạo

## Voiceover Mode

- [ ] Silent Product Voiceover tạo script tiếng Việt
- [ ] TTS tạo audio hoặc fallback rõ ràng
- [ ] Voiceover không quá dài so với video
- [ ] Voiceover được mix với original audio/BGM

## Render

- [ ] Render video có caption Việt
- [ ] Overlay/subtitle style đúng
- [ ] BGM được mix
- [ ] Original audio giữ lại nếu bật
- [ ] Render lỗi có `failed_step` rõ
- [ ] Một video lỗi không crash toàn batch

## Final QA + Export

- [ ] Final QA chạy sau render
- [ ] QA score hiển thị
- [ ] Export Pack tạo đủ folder
- [ ] `videos/` có video final
- [ ] `subtitles/` có corrected SRT/ASS
- [ ] `logs/` có log JSON
- [ ] `qa/` có QA report
- [ ] `posting_checklist.md` được tạo
- [ ] `export_manifest.json` đúng

