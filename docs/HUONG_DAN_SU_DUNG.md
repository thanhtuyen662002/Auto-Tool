# 📖 Hướng Dẫn Sử Dụng Auto Tool Studio

> **Phiên bản:** v1.0.0-rc1 | **Ngôn ngữ:** Tiếng Việt | **Hệ điều hành:** Windows

---

## 📋 Mục Lục

1. [Auto Tool là gì?](#1-auto-tool-là-gì)
2. [Cài đặt và khởi chạy](#2-cài-đặt-và-khởi-chạy)
3. [Thiết lập ban đầu](#3-thiết-lập-ban-đầu)
4. [Hướng dẫn cơ bản — Douyin Reup](#4-hướng-dẫn-cơ-bản--douyin-reup)
5. [Hướng dẫn trung cấp — Xem và chỉnh sửa phụ đề](#5-hướng-dẫn-trung-cấp--xem-và-chỉnh-sửa-phụ-đề)
6. [Hướng dẫn nâng cao — Silent Mode](#6-hướng-dẫn-nâng-cao--silent-mode)
7. [Hướng dẫn nâng cao — Tạo video sản phẩm từ đầu](#7-hướng-dẫn-nâng-cao--tạo-video-sản-phẩm-từ-đầu)
8. [Tính năng bổ sung](#8-tính-năng-bổ-sung)
9. [Xử lý sự cố thường gặp](#9-xử-lý-sự-cố-thường-gặp)
10. [Lưu ý pháp lý và sử dụng hợp lệ](#10-lưu-ý-pháp-lý-và-sử-dụng-hợp-lệ)

---

## 1. Auto Tool là gì?

**Auto Tool Studio** là ứng dụng chạy hoàn toàn trên máy tính của bạn (không cần kết nối cloud) để hỗ trợ xử lý và dựng lại video, đặc biệt là video Douyin (TikTok Trung Quốc) sang phiên bản tiếng Việt.

### Bạn có thể làm gì với Auto Tool?

| Tính năng | Mô tả |
|-----------|-------|
| 🎬 **Douyin Reup** | Lấy video Douyin đã tải về → dịch phụ đề Trung sang Việt → render video mới |
| 🔇 **Silent Mode** | Xử lý video không có lời thoại → tạo caption tiếng Việt → thêm giọng đọc nếu muốn |
| 🛒 **Tạo video sản phẩm** | Tạo video quảng cáo sản phẩm từ folder video nguồn với script AI |
| 📦 **Nhập sản phẩm** | Import thông tin sản phẩm từ Shopee qua Chrome Extension |
| ✏️ **Review phụ đề** | Xem, sửa, duyệt từng dòng phụ đề trước khi render |

### Auto Tool **KHÔNG** làm những gì?

- ❌ Không tự tải video từ Douyin/TikTok
- ❌ Không xóa watermark khỏi video
- ❌ Không tự đăng bài lên mạng xã hội
- ❌ Không đăng nhập tài khoản bất kỳ nền tảng nào

---

## 2. Cài đặt và khởi chạy

### Cách đơn giản nhất — Dùng file EXE

1. **Tải file `AutoTool.exe`** từ nguồn được cung cấp
2. **Copy toàn bộ thư mục `AutoTool/`** (bao gồm `AutoTool.exe` và thư mục `_internal/`) sang nơi bạn muốn lưu — ví dụ: `D:\AutoTool\`
3. **Double-click vào `AutoTool.exe`**
4. Lần đầu khởi chạy: app sẽ tự mở trình duyệt web tại địa chỉ `http://localhost:8000`
5. Giao diện web sẽ hiện ra — bạn đã sẵn sàng!

> **💡 Lưu ý lần đầu chạy:** Nếu trình duyệt chưa tự mở sau 5-10 giây, hãy mở trình duyệt và gõ: `http://localhost:8000`

> **⚠️ Quan trọng:** Không đóng cửa sổ đen (Command Prompt) đang chạy AutoTool — đó là server đang hoạt động. Chỉ đóng khi bạn muốn tắt app.

---

## 3. Thiết lập ban đầu

Trước khi bắt đầu, hãy vào **Settings** (Cài đặt) để cấu hình:

### 3.1. Thêm Gemini API Key

Auto Tool dùng Google Gemini AI để **dịch phụ đề** và **tạo script video**. Bạn cần ít nhất 1 API key miễn phí.

**Lấy Gemini API Key miễn phí:**
1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập Google → Nhấn **"Create API key"**
3. Copy key vừa tạo

**Nhập key vào Auto Tool:**
1. Mở Auto Tool → Vào **Settings** (biểu tượng bánh răng)
2. Tìm mục **"Gemini API Keys"**
3. Paste key vào ô trống, mỗi key một dòng
4. Nhấn **Lưu**

> **💡 Mẹo:** Tạo 2-3 key khác nhau để tránh bị giới hạn khi dịch nhiều video.

### 3.2. Kiểm tra trạng thái hệ thống

Vào **Settings → Hệ thống** để xem:
- ✅ FFmpeg: đã cài (tự động)
- ✅ Piper TTS: đã cài (tự động)
- ✅ Voice tiếng Việt: đã cài (tự động)

Nếu thiếu, app sẽ tự tải về khi cần.

---

## 4. Hướng dẫn cơ bản — Douyin Reup

> **Dành cho:** Người mới bắt đầu, lần đầu dùng tool

### Yêu cầu trước khi bắt đầu

- Video Douyin đã **tải về máy tính** (định dạng: `.mp4`, `.mov`, `.mkv`, `.webm`)
- Có **Gemini API Key** đã thêm vào Settings
- Thư mục chứa video và thư mục đầu ra đã tạo sẵn

### Bước 1 — Mở trang Douyin Reup

Trên thanh menu trái, nhấn vào **"Douyin Reup"**

### Bước 2 — Chọn thư mục và cấu hình

Điền vào form:

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| **Thư mục video nguồn** | Folder chứa video Douyin đã tải | `D:\Videos\douyin` |
| **Thư mục đầu ra** | Folder sẽ lưu video đã xử lý | `D:\Videos\outputs` |
| **Nhạc nền (tùy chọn)** | Folder chứa file nhạc `.mp3` | `D:\Music\bgm` |

### Bước 3 — Chọn Preset (Bộ cài đặt)

Nhấn **"Chọn preset"** và chọn một trong các tùy chọn:

| Preset | Khi nào dùng? |
|--------|--------------|
| 🟢 **Safe Review** *(Khuyên dùng lần đầu)* | Dịch phụ đề, dừng lại để bạn kiểm tra trước khi render |
| ⚡ **Fast Auto** | Tự động render ngay sau khi dịch, không cần kiểm tra |
| 👁️ **OCR Priority** | Video có chữ Trung in cứng trên màn hình (không có file .srt) |
| 🎤 **Voice Priority** | Video có lời thoại rõ, không có subtitle |
| 🎵 **Music Recut** | Render với nhạc nền to hơn, phong cách montage |
| 📝 **Clean Subtitle Only** | Chỉ burn subtitle, không thêm overlay hay nhạc |

**👉 Lần đầu dùng: chọn "Safe Review"**

### Bước 4 — Bắt đầu xử lý

Nhấn nút **"Bắt đầu One-click Batch"**

Tool sẽ tự động làm các bước:
```
📂 Quét video trong thư mục
   ↓
🔍 Phát hiện nguồn phụ đề (file .srt / phụ đề nhúng / nhận diện giọng nói)
   ↓
🈶 Trích xuất phụ đề tiếng Trung
   ↓
🌐 Dịch sang tiếng Việt (Gemini AI)
   ↓
⏸️ Dừng để bạn kiểm tra phụ đề (nếu dùng Safe Review)
```

Thanh tiến trình sẽ hiện lên — bạn có thể xem trạng thái từng bước.

---

## 5. Hướng dẫn trung cấp — Xem và chỉnh sửa phụ đề

> **Áp dụng sau khi Douyin Reup hoàn thành bước dịch**

### 5.1. Mở trang Review Phụ Đề

Sau khi job dịch xong với preset **Safe Review**, bạn sẽ thấy nút **"Review phụ đề"**. Nhấn vào đó hoặc vào menu **"Subtitle Review"**.

### 5.2. Đọc điểm chất lượng

Mỗi dòng phụ đề được chấm điểm tự động:

| Biểu tượng | Ý nghĩa |
|-----------|---------|
| 🔴 **Critical** | Lỗi nghiêm trọng — **bắt buộc phải sửa** |
| 🟡 **Warning** | Cần xem lại — nên sửa trước khi đăng |
| 🟢 **OK** | Dòng phụ đề ổn |

**Các lỗi thường gặp:**
- Còn sót chữ Trung trong bản dịch
- Dòng quá dài (đọc không kịp)
- Sai timing
- Câu dịch không tự nhiên

### 5.3. Sửa phụ đề

**Sửa thủ công:**
- Nhấn vào dòng cần sửa
- Chỉnh sửa text tiếng Việt trong ô bên phải
- Nhấn **Lưu**

**Dùng gợi ý tự động:**
- Nhấn nút **"Suggest rewrite"** bên cạnh dòng bị flag
- Tool tạo 2-3 phiên bản ngắn hơn, tính trước điểm chất lượng
- Chọn phiên bản phù hợp → **"Apply"**

### 5.4. Duyệt và Render

Sau khi kiểm tra xong:
1. Nhấn **"Approve"** (Duyệt) ở đầu trang
2. Nhấn **"Render video đã duyệt"**
3. Chờ render hoàn thành
4. Video đầu ra sẽ ở trong thư mục đầu ra bạn đã chỉ định

### 5.5. Kiểm tra Final QA

Sau khi render, tab **"Final QA"** sẽ hiện báo cáo kỹ thuật:
- ✅ Độ phân giải đúng (1080×1920)
- ✅ Tỷ lệ 9:16
- ✅ FPS 30
- ✅ Codec H.264/AAC
- ✅ Subtitle đã được burn vào video

> **⚠️ Quan trọng:** Final QA chỉ kiểm tra kỹ thuật, bạn vẫn nên **xem lại video bằng mắt** trước khi đăng!

### 5.6. Tạo Export Pack

Nhấn **"Tạo Export Pack"** để đóng gói video kèm theo:
- File video đã render
- File phụ đề `.srt`
- Caption text cho TikTok/Reels
- Checklist đăng bài

---

## 6. Hướng dẫn nâng cao — Silent Mode

> **Dành cho:** Video không có lời thoại (unboxing, demo sản phẩm, cảnh đẹp)

### Khi nào dùng Silent Mode?

- Video Douyin **không có lời thoại** (chỉ có tiếng nhạc, âm thanh thao tác)
- Video sản phẩm kiểu "trưng bày", không có người nói
- Muốn tạo caption mô tả cảnh vật thay vì dịch lời thoại

### Các preset Silent Mode

| Preset | Phù hợp với |
|--------|------------|
| 🌿 **Chill Immersive** | Video phong cảnh, không gian sống, ASMR |
| 🎙️ **Product Voiceover** | Video sản phẩm cần giọng đọc tiếng Việt mới |
| ⚡ **Sales Recut** | Clip sản phẩm cần caption bán hàng nhanh |

### Các bước thực hiện

1. Vào menu **"Silent Mode"**
2. Chọn thư mục video và thư mục đầu ra
3. Chọn **ngành hàng** (ví dụ: điện tử, thời trang, gia dụng)
4. Thêm **thông tin sản phẩm** nếu có (tên sản phẩm, tính năng chính)
5. Chọn preset phù hợp
6. Nhấn **"Bắt đầu"**

Tool sẽ:
- Phân tích xem video có lời thoại không
- Phân đoạn hình ảnh
- OCR chữ Trung trên màn hình (nếu có)
- Tạo caption tiếng Việt theo template ngành hàng
- (Tùy chọn) Tạo giọng đọc tiếng Việt

---

## 7. Hướng dẫn nâng cao — Tạo video sản phẩm từ đầu

> **Dành cho:** Tạo video quảng cáo sản phẩm từ video nguồn của riêng bạn

### 7.1. Nhập sản phẩm từ Shopee (Chrome Extension)

Nếu bạn đã cài **Shopee Chrome Extension**:
1. Mở trang sản phẩm trên Shopee
2. Nhấn vào Extension Auto Tool
3. Nhấn **"Gửi sang Auto Tool"**
4. Vào menu **"Import Inbox"** trong app để xem sản phẩm vừa nhập
5. Chỉnh sửa thông tin nếu cần → **"Tạo project mới"**

### 7.2. Tạo project thủ công

1. Vào menu **"Dashboard"** → **"Tạo project mới"**
2. Điền thông tin:
   - Tên sản phẩm
   - Thư mục video nguồn
   - Số lượng video muốn tạo
   - Độ dài video đầu ra (giây)
3. Chọn **Industry Preset** (Bộ cài đặt ngành hàng)
4. Nhấn **"Tạo project"**

### 7.3. Cấu hình Render Settings

Trong trang **Render Settings** của project:

**Phụ đề và Voiceover:**
- Bật/tắt subtitle
- Chọn giọng đọc (Edge TTS online / Piper offline / gTTS)
- Chọn giọng nữ (`vi-VN-HoaiMyNeural`) hoặc giọng nam

**Nhạc nền:**
- Chọn thư mục nhạc nền
- Điều chỉnh âm lượng nhạc (0–100%)
- Âm lượng giọng đọc (0–100%)

**Hiệu ứng:**
- Cường độ cắt ghép (nhẹ → mạnh)
- Thêm overlay/banner phía dưới

**Giải quyết:**
- Chuẩn 9:16 (1080×1920) cho TikTok/Reels/Shorts

### 7.4. Render Preview (Xem thử)

1. Nhấn **"Render Preview"** để tạo 1 video ngắn (xem trước)
2. Xem video → đánh giá
3. Nếu muốn chỉnh script: nhấn **"Sửa script"** → thay đổi → **"Lưu script tùy chỉnh"**
4. Khi hài lòng → nhấn **"Render Full Batch"**

### 7.5. Render Full Batch

- App sẽ tạo tất cả video theo số lượng bạn đã đặt
- Xem tiến trình trong **Render Queue**
- Kết quả ở tab **Results**

---

## 8. Tính năng bổ sung

### 8.1. Recovery Center

Nếu app bị đóng đột ngột giữa chừng khi đang render:
1. Mở lại App Tool
2. Vào **"Recovery Center"** (menu trái)
3. App sẽ phát hiện job bị gián đoạn
4. Chọn **"Resume"** để tiếp tục từ điểm dừng

### 8.2. Quản lý hàng đợi Batch dài

Khi đang render nhiều video, bạn có thể:
- ⏸️ **Tạm dừng** sau video hiện tại
- ▶️ **Tiếp tục** batch
- ⏭️ **Bỏ qua** video đang lỗi
- 🔄 **Retry** video đã lỗi
- ↕️ **Đổi thứ tự** video chưa render

### 8.3. Backup & Restore dữ liệu

Vào **Settings → Dữ liệu**:
- **Backup:** Tạo file backup nén chứa project, phụ đề, cài đặt
- **Restore:** Khôi phục từ file backup
- **Dọn dẹp:** Xóa cache, log tạm, file temp

> **💡 Khuyến nghị:** Backup trước khi cập nhật phiên bản mới

---

## 9. Xử lý sự cố thường gặp

### 🔴 App không mở / trình duyệt không tự mở

**Giải pháp:**
1. Đợi 10-15 giây sau khi double-click `AutoTool.exe`
2. Mở trình duyệt → gõ `http://localhost:8000`
3. Nếu vẫn không được, kiểm tra cửa sổ đen xem có thông báo lỗi không

---

### 🔴 Không dịch được — "Gemini translation failed"

**Nguyên nhân:** Thiếu API key hoặc key hết quota

**Giải pháp:**
1. Vào **Settings** → kiểm tra Gemini API Keys
2. Tạo thêm key mới tại https://aistudio.google.com/app/apikey
3. Thêm key mới vào danh sách (mỗi dòng 1 key)

---

### 🔴 Không tìm thấy video — "No video files found"

**Nguyên nhân:** Thư mục trống hoặc định dạng không hỗ trợ

**Giải pháp:**
- Video phải có định dạng: `.mp4`, `.mov`, `.mkv`, `.webm`
- Kiểm tra lại đường dẫn thư mục (không dùng ký tự đặc biệt)

---

### 🔴 Nhận diện giọng nói chậm / kém chính xác

**Nguyên nhân:** Model Whisper ASR đang tải về lần đầu (~100MB)

**Giải pháp:**
- Đợi lần đầu tải xong (chỉ cần tải 1 lần)
- Dùng preset **OCR Priority** nếu video có chữ Trung in trên màn hình
- Dùng file `.srt` đi kèm video (nhanh và chính xác nhất)

---

### 🔴 Render video lỗi — "Render failed"

**Giải pháp:**
1. Xem log chi tiết trong thư mục output → file `video_001_log.json`
2. Kiểm tra xem thư mục đầu ra có đủ dung lượng không (cần ~500MB–2GB)
3. Thử nhấn **Retry** cho video bị lỗi

---

### 🔴 OCR nhận diện sai chữ Trung

**Đây là hạn chế của công nghệ OCR**, đặc biệt khi:
- Chữ nhỏ hoặc mờ
- Chữ có animation/hiệu ứng
- Nền phức tạp

**Giải pháp:**
- Sau khi dịch, mở **Subtitle Review** để kiểm tra và sửa thủ công
- Nếu có sẵn file `.srt` tiếng Trung, đặt cùng thư mục với video (ưu tiên hơn OCR)

---

### 🔴 Giọng đọc không có âm thanh

**Giải pháp:**
- Kiểm tra kết nối internet (Edge TTS cần mạng)
- Nếu mất mạng, app sẽ tự chuyển sang Piper (offline) — không cần làm gì thêm
- Vào Settings → kiểm tra trạng thái Piper TTS

---

## 10. Lưu ý pháp lý và sử dụng hợp lệ

> **⚠️ Đọc kỹ trước khi sử dụng**

### Bạn CHỈ được phép dùng Auto Tool với:

- ✅ Video do bạn tự quay
- ✅ Video mua bản quyền hoặc được cấp phép thương mại
- ✅ Video có giấy phép Creative Commons cho phép remix
- ✅ Nhạc nền có bản quyền thương mại (royalty-free)

### Bạn KHÔNG được phép:

- ❌ Reupload video của người khác mà không có sự cho phép
- ❌ Xóa hoặc bypass watermark của tác giả gốc
- ❌ Tạo nội dung có thông tin sai (thông số kỹ thuật bịa đặt)
- ❌ Dùng claim tuyệt đối không có bằng chứng: "tốt nhất", "số 1", "100% hiệu quả"
- ❌ Vi phạm điều khoản của TikTok, Shopee, Instagram, YouTube

### Trách nhiệm của người dùng

- Luôn **xem lại video** trước khi đăng công khai
- Kiểm tra **bản dịch tự động** — AI có thể dịch sai hoặc không tự nhiên
- Đảm bảo **caption và script** không chứa thông tin gây hiểu nhầm
- Tuân thủ chính sách nội dung của nền tảng bạn đăng

---

## 📞 Hỗ trợ & Tài liệu thêm

| Tài liệu | Mô tả |
|----------|-------|
| `docs/TROUBLESHOOTING.md` | Tài liệu xử lý lỗi chi tiết |
| `docs/CRASH_RECOVERY_JOB_RESUME.md` | Hướng dẫn Recovery Center |
| `RELEASE_NOTES.md` | Ghi chú phiên bản |

---

*Tài liệu này được viết cho Auto Tool Studio v1.0.0-rc1.*
*Cập nhật lần cuối: Tháng 6/2026*
