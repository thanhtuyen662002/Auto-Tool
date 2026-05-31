# Auto Tool Development Plan

Tài liệu này mô tả các phase phát triển chính của Auto Tool để developer mới có thể hiểu thứ tự ưu tiên và phạm vi từng giai đoạn.

## Phase 1: CLI MVP

Mục tiêu: có pipeline local chạy được bằng CLI.

Phạm vi:

- Đọc config JSON bằng Pydantic.
- Resolve path tương đối sang absolute path.
- Scan video input folder.
- Lấy metadata bằng `ffprobe`.
- Bỏ qua video lỗi hoặc quá ngắn.
- Cắt video thành segment cơ bản theo `cut_intensity`.
- Build timeline random cho nhiều output.
- Render visual recut bằng FFmpeg.
- Xuất output folder và `project_summary.json`.

Tiêu chí hoàn thành:

- Lệnh `py -m app.main --config ../examples/product_config.example.json` chạy được.
- Có ít nhất một video output hợp lệ.
- Lỗi FFmpeg/config/path có message dễ hiểu.

## Phase 2: Gemini + Subtitle + Voice

Mục tiêu: biến video recut thành video có script, voice, subtitle và overlay.

Phạm vi:

- Gemini adapter có timeout, retry, JSON parsing và key rotation.
- Prompt cố định yêu cầu JSON schema rõ.
- Script writer tạo script khác nhau cho từng output.
- Fallback script chỉ dùng khi debug/offline.
- TTS tiếng Việt qua provider system: Edge TTS, Piper offline, gTTS backup, silent fallback.
- Retry Edge TTS nhẹ rồi tự chuyển provider fallback; silent vẫn là fallback cuối để giữ pipeline render được khi cần debug.
- Subtitle `.srt` để debug và `.ass` để burn.
- Overlay đáy video.
- CTA ở cuối script.
- Music background optional.

Tiêu chí hoàn thành:

- Mỗi output có `video_XXX_script.json`, `video_XXX_sub.srt`, `video_XXX_voice.mp3` hoặc `.wav` tùy TTS provider/config.
- Sub và voice dùng cùng timeline.
- Nếu subtitle burn lỗi, output vẫn có thể render fallback và ghi warning.

## Phase 3: FastAPI

Mục tiêu: frontend và exe có thể điều khiển backend qua API local.

Phạm vi:

- Tạo project bằng `POST /api/projects`.
- Lưu project/job/log bằng SQLite.
- Scan video qua API.
- Start render background thread.
- Poll job status.
- Lấy results.
- Preset endpoint.
- Health check endpoint.
- CORS cho frontend local.
- Không thay thế CLI.

Tiêu chí hoàn thành:

- API không block khi render.
- Job status có progress/logs.
- Batch không crash toàn bộ khi một output lỗi.

## Phase 4: React UI

Mục tiêu: người dùng không cần dùng terminal cho workflow chính.

Phạm vi:

- CreateProjectPage.
- RenderSettingsPage.
- RenderQueuePage.
- ResultPage.
- Product form.
- Preset selector.
- Effect sliders.
- Config preview.
- Result list.
- API client dùng `fetch`.
- Error box rõ ràng.

Tiêu chí hoàn thành:

- User nhập folder path local, lưu project, scan, render và xem kết quả được.
- UI hiển thị lỗi API rõ.
- Không mock API khi backend đã có.

## Phase 5: Preview Mode

Mục tiêu: render thử nhanh trước khi render full batch.

Phạm vi:

- `preview_only=true` trong endpoint render.
- Preview chỉ render 1 video.
- Duration preview là `min(config.render.duration, 8)`.
- Output preview nằm trong `{output_folder}/preview`.
- Lưu latest script.
- Cho phép chỉnh custom script qua `PUT /api/projects/{project_id}/script`.
- Full batch dùng custom script nếu có.
- Frontend hiển thị preview video và editor script đơn giản.

Tiêu chí hoàn thành:

- Preview không ghi đè output full batch.
- Custom script invalid trả lỗi rõ.
- Sau preview có thể sửa script rồi render full batch.

## Phase 6: Smart Segment

Mục tiêu: thay segment random cơ bản bằng segment có chất lượng tốt hơn.

Ý tưởng triển khai:

- Phân tích motion score.
- Phân tích blur/sharpness.
- Ưu tiên đoạn có ánh sáng ổn.
- Tránh đoạn transition lỗi hoặc quá tối.
- Scene boundary detection cơ bản bằng FFmpeg filters hoặc OpenCV.
- Chấm điểm segment theo nhiều tiêu chí.
- Cache metadata/score để render lại nhanh hơn.

Tiêu chí hoàn thành:

- Segment có `score` có ý nghĩa thay vì random.
- Timeline ít dùng đoạn mờ, tối hoặc lặp.
- Vẫn giữ fallback khi phân tích nâng cao lỗi.

## Phase 7: Product-aware Timeline

Mục tiêu: timeline hiểu mục tiêu quảng cáo sản phẩm thay vì chỉ ghép clip ngẫu nhiên.

Ý tưởng triển khai:

- Gắn tag segment: close-up, usage, detail, lifestyle, packaging, CTA.
- Dựa vào product features để chọn đoạn phù hợp.
- Timeline có cấu trúc: hook, problem, feature, proof, CTA.
- Mỗi output có angle riêng.
- Tránh dùng một source quá nhiều liên tục.
- Đồng bộ nhịp cut với script/voiceover.
- Chuẩn bị chỗ cho overlay ảnh sản phẩm hoặc template.

Tiêu chí hoàn thành:

- Video output khác nhau rõ về góc tiếp cận.
- Script và visual khớp nội dung hơn.
- Có cấu trúc timeline dễ debug trong log.

## Nguyên Tắc Phát Triển

- CLI vẫn phải chạy được sau khi thêm API/UI.
- Không nuốt lỗi; lỗi phải có message rõ.
- Batch không fail toàn bộ vì một output lỗi.
- Log chi tiết nằm trong file, UI chỉ hiển thị lỗi ngắn.
- Ưu tiên MVP chạy ổn trước khi thêm thuật toán phức tạp.
- Không thêm provider mới nếu chưa có interface rõ.
- Không bypass watermark hoặc tạo workflow vi phạm bản quyền.
