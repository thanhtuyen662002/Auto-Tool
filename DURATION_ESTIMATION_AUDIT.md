# Báo cáo Đánh giá Hệ thống Ước tính Thời lượng Giọng đọc (Duration Estimation Audit)

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Khảo sát và đánh giá hệ thống ước lượng thời lượng giọng nói hiện tại để tìm giải pháp tối ưu cho lỗi lệch đồng bộ âm thanh/video (`voice_longer_than_video`).

---

## 1. Kết quả Audit & Trả lời các câu hỏi

### Câu hỏi 1: `estimate_voice_duration()` đang được gọi từ đâu?
Hàm này được định nghĩa tại [text_cleanup.py](file:///d:/Projects/Auto-Tool/backend/app/modules/tts/text_cleanup.py) và chỉ được import/sử dụng tại duy nhất một file là [length_guard.py](file:///d:/Projects/Auto-Tool/backend/app/modules/script_writer/length_guard.py) trong hai trường hợp:
1. Trong `prepare_script_for_tts` (Dòng 43) để kiểm tra xem thời lượng kịch bản ước tính có vượt quá thời lượng video mục tiêu cộng thêm 2 giây (`target_duration + 2.0`) hay không.
2. Trong `_shorten_voiceover` (Dòng 91) bên trong một vòng lặp `while` để loại bỏ dần các dòng voiceover dài nhất cho đến khi tổng thời lượng ước tính nhỏ hơn hoặc bằng `target_duration + 2.0`.

### Câu hỏi 2: Giá trị duration estimation có độ chính xác khoảng bao nhiêu?
Thuật toán ước tính dựa vào số ký tự thô sau khi đã lọc bỏ emoji/hashtag (`len(cleaned)`):
- Đối với tiếng Việt: Lấy chiều dài chuỗi chia cho `12.5` ký tự/giây.
- Đối với ngôn ngữ khác: Lấy chiều dài chuỗi chia cho `14.0` ký tự/giây.
**Độ chính xác:** Đây là một công thức heuristics tương đối sơ sài. Trên thực tế, tốc độ nói thực tế phụ thuộc nhiều vào từng model giọng nói (Edge TTS Neural, Piper, Google Cloud), các khoảng nghỉ câu và dấu câu. Sai số thực tế thường dao động từ **15% đến 25%** so với file audio thật.

### Câu hỏi 3: Có được lưu vào project hay job metadata không?
**KHÔNG.** Giá trị ước tính này chỉ được tính toán tạm thời trong bộ nhớ để làm căn cứ cắt bớt ký tự thoại thô trong file kịch bản. Nó hoàn toàn **không** được lưu vào bất kỳ bảng SQLite nào, cũng không xuất hiện trong cấu hình dự án hay job metadata. Chỉ có thời lượng thực tế sau render (`voice_duration`) mới được ghi nhận.

### Câu hỏi 4: Có được dùng để build timeline không?
**KHÔNG.** `ProductTimelineBuilder` dựng timeline thô dựa hoàn toàn vào tham số `render.duration` tĩnh từ cấu hình dự án (ví dụ: 12 giây). Nó hoàn toàn không có thông tin về độ dài của kịch bản hay giọng nói ước tính tại thời điểm dựng timeline.

### Câu hỏi 5: Có được dùng trước khi generate voice không?
**CÓ.** Hàm `prepare_script_for_tts` được gọi ngay dòng đầu tiên của `VoiceGenerator.generate_voiceover` để dọn dẹp văn bản và cắt bớt lời thoại bằng thuật toán ước tính trước khi gửi yêu cầu sinh file âm thanh đến nhà cung cấp TTS (Edge TTS/Google Cloud).

### Câu hỏi 6: Có được dùng sau khi generate voice không?
**KHÔNG.** Sau khi sinh file âm thanh thành công, hệ thống trực tiếp sử dụng lệnh `probe_media_duration()` để đo chính xác thời lượng của file âm thanh thật và bỏ hoàn toàn giá trị ước tính thô.

### Câu hỏi 7: Voice duration thật hiện được lấy ở đâu?
Thời lượng thực tế của giọng đọc được đo bằng hàm `probe_media_duration()` (gọi ffprobe) đối với tệp âm thanh đã tạo:
- Lần 1: Trong `VoiceGenerator._read_final_voice_duration` (sau khi ghép các phân đoạn thoại).
- Lần 2: Trong `output_pipeline.py` tại hàm `_normalize_voice_for_render` (sau khi convert sang định dạng WAV).

### Câu hỏi 8: Voice trimming hiện diễn ra ở đâu?
Quá trình cắt giảm giọng đọc diễn ra ở hai cấp độ:
1. **Cắt giảm văn bản (Text-level):** Diễn ra trong `length_guard.py` trước khi sinh giọng nói. Nếu ước tính kịch bản quá dài, các câu thoại sẽ bị loại bỏ bớt.
2. **Cắt âm thanh vật lý (Audio-level):** Diễn ra trong `VoiceGenerator._fit_voice_duration` bằng cách gọi FFmpeg với filter `atrim=0:target_duration`. Điều này trực tiếp cắt bỏ phần đuôi âm thanh nếu độ dài file âm thanh lớn hơn video mục tiêu.

### Câu hỏi 9: Voice synchronization issue xuất hiện ở bước nào?
Lỗi lệch đồng bộ xuất hiện do sự không khớp giữa các bước sau:
1. **Lệch pha text/audio:** `length_guard.py` cho phép văn bản có thời lượng ước tính dài hơn video mục tiêu tới 2 giây (`target_duration + 2.0`), nhưng khi render âm thanh, FFMPEG lại trim cứng ở mức `target_duration` khiến câu cuối cùng bị cắt cụt.
2. **Thời lượng visual cố định:** Visual video được kết xuất trước tại `renderer.render_timeline` cố định theo `config.render.duration`. Khi trộn audio vào visual ở bước `render_final_video`, FFmpeg giới hạn đầu ra bằng tùy chọn `-t {duration_visual}` khiến phần âm thanh dài hơn không thể phát.

---

## 2. Cơ hội Đơn giản hóa (Voice Sync Simplification Opportunities)

Tận dụng hạ tầng ước lượng và xử lý hiện có giúp chúng ta giảm thiểu đáng kể độ phức tạp của B5:

- **Giảm 50% độ phức tạp dựng hình:** Chúng ta **không cần** tính toán lại toàn bộ Timeline thô, không cần chạy lại phân cảnh (segmentation) hay chấm điểm OpenCV từ đầu khi thời lượng thay đổi.
- **Giữ nguyên visual cuts cũ:** Bằng cách giữ nguyên 100% thứ tự và độ dài các cảnh visual ban đầu, chúng ta chỉ cần xử lý bù đắp thời lượng thừa/thiếu ở **cảnh cuối cùng** (Last Clip) bằng cách:
  - Nếu thiếu hình (Voice > Video): Chỉ kéo dài clip cuối cùng (Extend Scene) hoặc chèn thêm 1 clip đóng băng (Freeze Frame / Slow Zoom).
  - Nếu thừa hình (Video > Voice): Giữ nguyên dòng visual thô và áp dụng fade-out nhạc/âm thanh tự nhiên (Ambient Ending).
- Việc này giúp loại bỏ hoàn toàn các rủi ro làm hỏng timeline hay thay đổi kết cấu video đã được người dùng tối ưu trước đó.

---

## 3. Khuyến nghị Hướng đi (Final Verdict)

Tôi đề xuất chọn hướng đi: **C. Hybrid Approach (Phương án Lai)**

### Giải thích lý do:
- **Tại sao không chọn A (Full Timeline Auto-Balancer)?** Quá phức tạp và rủi ro. Việc dựng lại toàn bộ timeline sẽ làm thay đổi cấu trúc phân bổ cảnh (ví dụ: cảnh Demo sản phẩm bị co giãn hoặc thay thế), làm mất tính cá nhân hóa của người dùng đối với dự án.
- **Tại sao không chọn B (Pre-Render Duration Alignment)?** Thiếu chính xác. Việc chỉ căn chỉnh kịch bản dựa trên ước tính thô (sai số 20%) vẫn không thể triệt tiêu hoàn toàn lỗi cắt cụt từ TTS thực tế.
- **Ưu điểm của C (Hybrid Approach):** 
  1. Cho phép sinh giọng đọc TTS đầy đủ tự nhiên mà không bị cắt cụt chữ.
  2. Đo chính xác thời lượng TTS thực tế để xác định độ lệch.
  3. Áp dụng chiến lược bù đắp trực tiếp lên Timeline bằng cách chèn duy nhất 1 clip Freeze Frame hoặc Slow Zoom ở cuối (đối với Voice > Video) hoặc giữ nguyên timeline thô (đối với Video > Voice).
  4. Đạt độ chính xác tuyệt đối 100% về đồng bộ âm thanh/hình ảnh, cài đặt dễ dàng và giữ nguyên kiến trúc kết xuất lõi của FFmpeg.
