# Silent Mode v1.0.0-rc1 Test Pack

Đặt video local mà bạn có quyền sử dụng vào:

```txt
sample_videos/silent_mode_v1_rc/
```

Không commit video thật vào repository. Kết quả được ghi vào `examples/outputs/silent_mode_v1_rc/`.

## Dataset tối thiểu

- 5 video không thoại chỉ có nhạc
- 5 video có tiếng thao tác hoặc mở hộp
- 5 video có chữ Trung dính màn hình
- 3 video gia dụng hoặc nhà bếp
- 3 video setup bàn hoặc góc làm việc
- 3 video lưu trữ hoặc dọn dẹp
- 3 video làm đẹp hoặc phụ kiện
- 2 video không có audio
- 2 video ngang hoặc vuông
- 2 video ngắn dưới 8 giây
- 2 video dài trên 30 giây
- 1 file video lỗi nếu có thể

Một video có thể thuộc nhiều nhóm. Dataset cần phủ Silent detection, visual segmentation, visual tagging, OCR/template caption, tag override, caption regeneration, Subtitle Review, render, Final QA và Export Pack.

## Chạy RC

Từ folder `backend`:

```powershell
python -m app.tools.silent_mode_v1_rc_test --config ../examples/silent_mode_v1_rc/configs/silent_v1_chill_immersive.json
```

Test nhanh không phụ thuộc OCR/TTS thật:

```powershell
python -m app.tools.silent_mode_v1_rc_test --config ../examples/silent_mode_v1_rc/configs/silent_v1_kitchen_goods.json --mock-ocr --mock-tts --review-mode
```

Render, Final QA và Export Pack:

```powershell
python -m app.tools.silent_mode_v1_rc_test --config ../examples/silent_mode_v1_rc/configs/silent_v1_chill_immersive.json --auto-render --final-qa --export-pack
```

Flags: `--preset`, `--industry`, `--scan-only`, `--detect-only`, `--plan-only`, `--review-mode`, `--auto-render`, `--final-qa`, `--export-pack`, `--mock-ocr`, `--mock-tts`, `--debug`.

Không dùng `--debug` trong QA thông thường: terminal chỉ in lỗi thân thiện. `--debug` dành cho kỹ thuật viên cần traceback.

