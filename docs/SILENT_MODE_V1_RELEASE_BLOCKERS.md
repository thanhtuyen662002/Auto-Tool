# Silent Mode v1 Release Blockers

## Block release

- App crash toàn batch khi một video lỗi.
- Silent preset không tạo được plan cho video hợp lệ.
- Caption generation không tạo được caption nào.
- Subtitle Review không lưu được caption.
- Approve không tạo corrected SRT/ASS.
- Render không dùng corrected caption.
- Render không tạo output video với input hợp lệ.
- Final video mất audio khi settings yêu cầu giữ audio.
- Export Pack thiếu video final.
- Job queue bị kẹt, không chuyển sang completed hoặc failed.
- Frontend trắng màn hình ở flow chính.
- Lỗi không có log hoặc message đủ rõ để xử lý.

## Does not block release

- Caption hơi chung khi thiếu product context.
- Một số segment bị đoán sai tag nhưng user sửa được.
- OCR sai ở chữ nhỏ, mờ hoặc nền phức tạp.
- Template caption chưa hoàn hảo và cần user review.

Các điểm không block phải được ghi trong Known Limitations và report QA thủ công.

## Decision rule

RC chỉ được đánh dấu `Pass` khi không còn blocker mở. `Pass with warnings` chỉ áp dụng cho hạn chế chất lượng đã có đường sửa thủ công, không áp dụng cho mất dữ liệu, crash, render sai caption hoặc batch bị kẹt.

