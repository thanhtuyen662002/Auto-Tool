# Start Workflow UI QA Checklist

Prompt 49 scope: Douyin Reup and Silent Mode start workflow.

- [x] Douyin Reup page mở được
- [x] Silent Mode page mở được
- [x] Source folder card dễ hiểu
- [x] Scan folder hiển thị loading/success/error
- [x] Preset cards hiển thị đúng
- [x] Chọn preset active rõ
- [x] Right workflow preview cập nhật khi đổi preset
- [x] Output folder card hoạt động
- [x] Music folder optional rõ
- [x] Silent Mode có industry/tone
- [x] Product context optional collapsed
- [x] Advanced Settings mặc định đóng
- [x] Start checklist hiển thị missing/warning/ok
- [x] Start button disabled khi thiếu thông tin
- [ ] Start button loading khi tạo job
- [ ] Start job thành công có điều hướng rõ
- [x] Backend offline/scan error hiển thị thân thiện
- [x] Fast Auto có confirm nhẹ
- [x] Recent folders hoạt động
- [x] UI không rối trên laptop nhỏ
- [x] UI không tràn ngang trên mobile
- [x] Frontend build không lỗi

Notes:
- Browser QA đã chạy trên `/douyin-reup`, `/silent-mode`, viewport 1024x768 và 390x844.
- Scan success đã kiểm tra với `D:/Data/Auto-Tool/examples/sample_project/sample_videos/sample_product`, nhận 3 video mẫu và enable start button.
- Scan error đã kiểm tra với folder không tồn tại, checklist giữ start button disabled và hiện lỗi thân thiện.
- Chưa bấm nút confirm `Tiếp tục` để tạo job thật, nhằm tránh chạy pipeline xử lý video ngoài ý muốn trong QA UI.
