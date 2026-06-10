# Douyin Reup v1.0 Release Blockers

Release bị block nếu có:

- App crash toàn batch khi 1 video lỗi
- Render không tạo được output với video hợp lệ
- Subtitle Review không save được
- Approve không tạo corrected SRT
- Render không dùng corrected subtitle
- Final video không có audio khi settings yêu cầu giữ audio
- Export Pack thiếu video final
- Job queue bị kẹt không thể hoàn thành/fail
- Frontend trắng màn hình ở flow chính
- Không có log/error message rõ khi lỗi

Không block release nếu:

- ASR nhận sai một số câu
- OCR sai chữ ở video mờ
- Bản dịch cần user sửa lại
- Subtitle quality score chưa hoàn hảo
- Platform profile chỉ là cảnh báo kỹ thuật

Các lỗi không block phải được ghi trong Known Limitations hoặc manual QA report.
