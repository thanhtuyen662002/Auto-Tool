# Silent Mode Real Batch QA Test Pack

Đặt video local mà bạn có quyền sử dụng vào:

```txt
sample_videos/silent_mode_test_pack/
```

Không commit video thật vào repository. Các config trong `configs/` dùng chung folder trên và ghi kết quả vào `examples/outputs/silent_mode_test_pack/`.

## Dataset tối thiểu

- 5 video không thoại chỉ có nhạc
- 5 video có tiếng thao tác hoặc unboxing
- 3 video có chữ Trung dính màn hình
- 3 video có chữ Trung trên nền phức tạp
- 3 video gia dụng hoặc nhà bếp
- 3 video setup phòng hoặc bàn làm việc
- 3 video làm đẹp hoặc phụ kiện
- 2 video không có audio
- 2 video ngang hoặc vuông
- 2 video ngắn dưới 8 giây
- 2 video dài trên 30 giây

Dataset cần phủ speech detection, visual segmentation, OCR fallback, caption template, review, voiceover, render, Final QA và Export Pack.

## Chạy test

Từ folder `backend`:

```powershell
python -m app.tools.silent_mode_e2e_test --config ../examples/silent_mode_test_pack/configs/silent_chill_immersive.json --review-mode
python -m app.tools.silent_mode_e2e_test --config ../examples/silent_mode_test_pack/configs/silent_product_voiceover.json --auto-render --final-qa --export-pack
```

Các flags: `--scan-only`, `--detect-only`, `--plan-only`, `--review-mode`, `--auto-render`, `--final-qa`, `--export-pack`, `--mock-ocr`, `--mock-tts`, `--debug`.

`--mock-ocr` tắt OCR thật để test nhánh template fallback. `--mock-tts` tắt voiceover thật để test render không phụ thuộc TTS.
