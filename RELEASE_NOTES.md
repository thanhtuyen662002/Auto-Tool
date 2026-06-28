# Auto Tool Douyin Reup v1.0.0-rc1

## v1.3.7

### Highlights

- **Cải tiến độ tin cậy của tính năng Cập Nhật Tự Động (Hotfix)**:
  - **Cưỡng bức đóng tiến trình con trước khi cập nhật**: Updater script (`_update.bat`) được bổ sung lệnh `taskkill /F /IM AutoTool.exe /T` để quét sạch toàn bộ tiến trình con chạy ngầm (nếu có) trước khi copy ghi đè file mới.
  - **Khắc phục lỗi treo tiến trình cập nhật ngầm**: Loại bỏ lệnh `pause` trong script khi gặp lỗi copy đè (do file bị khóa). Thay vào đó, ghi chi tiết lỗi vào tệp `update_error.log` và tự động thoát để tránh treo tiến trình cập nhật ngầm mãi mãi.

## v1.3.6

### Highlights

- **Sửa lỗi đơ/treo tiến trình ở mức 10% trong Silent Mode và hàng loạt (Hotfix)**:
  - **Khắc phục lỗi deadlock của multiprocessing.Queue**: Thay đổi cơ chế truyền thông điệp kết quả xử lý từ tiến trình con cô lập (isolated subprocess) về tiến trình cha từ việc sử dụng `multiprocessing.Queue` sang dùng tệp tin JSON tạm thời (`tempfile`).
  - **Lý do**: Khi dữ liệu kết quả phân tích video (bao gồm nhiều thông tin features, tagging, product candidate, QA reports) vượt quá dung lượng đệm của Pipe hệ điều hành, `multiprocessing.Queue.put()` sẽ bị chặn vĩnh viễn (deadlock) do tiến trình cha đang đợi `Process.join()` trước khi đọc Queue. Việc đổi sang ghi tệp tạm giúp loại bỏ hoàn toàn hiện tượng nghẽn luồng và đơ ở 10%.

## v1.3.5

### Highlights

- **Sửa lỗi không nhận dạng được chữ và crash trong quá trình chạy OCR (Hotfix)**:
  - **Sửa lỗi ValueError của NumPy**: Sửa lỗi `ValueError: The truth value of an array with more than one element is ambiguous` xảy ra trong quá trình chuẩn hóa tọa độ bounding box do PaddleOCR v3 trả về dạng NumPy array. Điều này khiến cả luồng OCR bị crash ngầm và trả về kết quả rỗng.
  - **Tắt các tác vụ xử lý văn bản tài liệu chuyên sâu**: Tắt các chức năng `use_doc_orientation_classify` và `use_doc_unwarping` của PaddleOCR. Điều này giúp ngăn chặn việc làm biến dạng (distortion) khung hình video (nhằm unwarp giấy tờ), khôi phục hoàn toàn khả năng phát hiện chữ chính xác của mô hình và tăng tốc độ xử lý CPU.

## v1.3.4

### Highlights

- **Khắc phục lỗi treo/đơ ứng dụng khi bắt đầu chạy Task (Hotfix)**:
  - **Nguyên nhân**: Khi bắt đầu chạy bất kỳ task reup nào, hàm kiểm tra `check_asr_support_and_optimize_settings` sẽ kiểm tra khả năng chạy của thư viện ASR (Whisper) bằng cách khởi tạo thử model `"tiny"` trên GPU và CPU. Nếu máy chưa có sẵn model `"tiny"` trong cache cục bộ, nó sẽ âm thầm tải model này từ Hugging Face. Việc tải model này qua mạng quốc tế thường bị nhà mạng Việt Nam chặn hoặc bóp băng thông, dẫn đến treo cứng ứng dụng lúc khởi động.
  - **Cách khắc phục**:
    1. Kiểm tra hỗ trợ GPU thông qua phương thức siêu tốc và không cần mạng `ctranslate2.get_cuda_device_count() > 0` thay vì load thử model `"tiny"`.
    2. Loại bỏ hoàn toàn bước khởi tạo test model trên CPU (mặc định CPU luôn khả dụng nếu import được thư viện).
    3. Giúp ứng dụng khởi động xử lý video ngay lập tức mà không bao giờ bị đơ/treo ở màn hình kiểm tra CUDA nữa.

## v1.3.3

### Highlights

- **Sửa triệt để lỗi treo/đơ và tăng tốc độ xử lý PaddleOCR (Hotfix)**:
  - **Sửa lỗi oneDNN instruction crash trên Windows CPU**: Vô hiệu hóa tính năng MKLDNN (`enable_mkldnn=False`) khi chạy trên CPU nhằm tránh lỗi không tương thích tập lệnh deep learning trên Windows.
  - **Tương thích toàn diện cấu trúc kết quả mới (v3.x / paddlex)**: Sửa đổi parser `_parse_paddle_blocks` để đọc chuẩn định dạng `rec_texts`/`rec_polys` của các phiên bản PaddleOCR mới, khắc phục lỗi không trả về kết quả chữ nào.
  - **Tốc độ xử lý hàng loạt (Batch Processing)**: Triển khai phương thức `recognize_batch` trong `PaddleOCRProvider` để chạy 4 frame cùng lúc, giúp tăng tốc độ trích xuất phụ đề lên gấp nhiều lần.
  - **Bỏ qua kiểm tra kết nối online**: Bật cấu hình `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` tránh việc PaddlePaddle kết nối liên tục ra server nước ngoài kiểm tra cập nhật model gây treo ứng dụng.

## v1.3.2

### Highlights

- **Sửa lỗi OCR đẩy iGPU lên 99% (Hotfix)**:
  - **Nguyên nhân**: `PaddleOCR` khi khởi tạo không truyền tham số `use_gpu`, dẫn đến PaddlePaddle tự động phát hiện và sử dụng card đồ họa tích hợp **Intel Iris Xe (iGPU)** qua DirectML để chạy model nhận dạng chữ. Điều này khiến iGPU bị đẩy lên **99% liên tục** trong suốt quá trình xử lý video.
  - **Cách khắc phục**: Cả `PaddleOCR` và `EasyOCR` giờ đây tự động kiểm tra sự hiện diện của card đồ họa rời **NVIDIA CUDA** thông qua `torch.cuda.is_available()` trước khi khởi tạo:
    - ✅ **Máy có card NVIDIA CUDA**: Tự động bật tăng tốc GPU trên card rời.
    - ✅ **Máy không có NVIDIA CUDA** (chỉ có iGPU Intel/AMD hoặc không có card rời): Ép chạy 100% bằng CPU, giải phóng hoàn toàn iGPU, máy không còn bị giật lag hay nóng máy.

## v1.3.1

### Highlights

- **Sửa lỗi Khởi động Ứng dụng (Hotfix)**:
  - Sửa lỗi cú pháp `SyntaxError: keyword argument repeated` bên trong file `preset_registry.py` do bị trùng lặp khối preset `silent_sales_recut` trong quá trình merge code trước đó.
  - Sửa lỗi khởi chạy ứng dụng ném ngoại lệ `ModuleNotFoundError: No module named 'app.modules.douyin_reup_presets.preset_registry'` khi đóng gói ứng dụng.

## v1.3.0

### Highlights

- **Bổ sung tính năng Chia nhỏ Video dài thông minh (Shorts/Reels/Tiktok)**:
  - **Thuật toán tìm điểm cắt thông minh (Subtitle-Aware Splitting)**: Phân tích file phụ đề tiếng Việt (SRT) sau khi render, tự động tìm khoảng lặng giữa các câu thoại gần giới hạn thời lượng nhất để cắt video. Tránh việc cắt cụt ngang lời nói của nhân vật cũ hoặc thuyết minh mới.
  - **Tự động vẽ nhãn số tập (Part/Episode Label Overlay)**: Vẽ nhãn số tập đè lên video. Người dùng tùy ý cấu hình vị trí, cỡ chữ, màu sắc chữ, màu sắc hộp nền và độ mờ nền của nhãn đè.
  - **Tự chọn thời lượng hiển thị nhãn tập**: Cho phép hiển thị xuyên suốt video hoặc chỉ hiện 5 giây đầu.
  - **Tự động lưu**: File sau khi chia nhỏ sẽ được lưu riêng tại thư mục con `split_parts` của video thành phẩm.

## v1.2.1

### Highlights

- **Bổ sung Tùy chọn Tỷ lệ Khung hình cho Video dài & Phim** (`LongVideoReupPage.tsx`):
  - Thêm hộp lựa chọn định dạng khung hình xuất trực quan:
    - **Tự động (Giữ nguyên kích thước phim gốc)**: Mặc định, giúp giữ nguyên độ phân giải gốc 16:9 hoặc 2.35:1 mà không bóp méo hình.
    - **Dọc (9:16)**: Tự động chèn blurred background (viền mờ) xung quanh video ngang cũ để biến thành video dọc, cực kỳ tiện lợi để đăng nhanh lên TikTok/Reels.
    - **Ngang (16:9)**: Ép về kích thước chuẩn màn hình rộng.
    - **Vuông (1:1)**.

## v1.2.0

### Highlights

- **Bổ sung tính năng Xử lý video dài & Phim độc lập** (Vlog, Phim dài):
  - **Giao diện thuần Việt**: Thêm tab **"Reup video dài/Phim"** vào Sidebar điều hướng, liên kết riêng trang `LongVideoReupPage.tsx` dễ dùng cho người Việt, không rành công nghệ.
  - **Cài đặt độc lập**: Cho phép cấu hình Việt Sub hoặc Thuyết minh lồng tiếng, tùy chỉnh âm lượng gốc của phim, bật/tắt nhạc nền (BGM) riêng để tránh chồng chéo lên cấu hình video ngắn.
  - **Bộ lọc tách thoại gốc (Vocal Removal)**: Sử dụng thuật toán đảo pha của FFmpeg trên CPU (hoặc tự động chuyển qua GPU Nvidia CUDA nếu phát hiện có card đồ họa) để triệt tiêu lời thoại của nhân vật gốc, giữ nguyên vẹn âm thanh và tiếng động môi trường.
  - **Phân vai giọng đọc thuyết minh (Multi-speaker)**: Cho phép chọn và lưu trữ giọng đọc riêng cho Người dẫn chuyện, Nhân vật Nam và Nhân vật Nữ (chuẩn bị cho lồng tiếng đa vai).

## v1.1.9

### Highlights

- **Bổ sung cảnh báo thời lượng video dài trong bước quét thư mục** (`douyin_folder_scanner.py`):
  - Tự động kiểm tra thời lượng video gốc khi quét nguồn.
  - Thêm cảnh báo trực quan nếu video dài trên 15 phút: `"Lưu ý: Video dài hơn 15 phút. Tiến trình xử lý trên CPU có thể tốn rất nhiều thời gian."`
  - Thêm cảnh báo nghiêm trọng nếu video dài trên 30 phút: `"Cảnh báo: Video dài hơn 30 phút. Quá trình quét OCR, dịch thuật và render trên CPU cực kỳ nặng, dễ gây lỗi timeout hoặc đơ máy."`
  - Hiển thị trực tiếp cảnh báo này trong trường `warnings` của video item trên UI trước khi người dùng tạo job xử lý.

## v1.1.8

### Highlights

- **Tăng tốc độ Render video trên CPU** (`douyin_render_pipeline.py`):
  - Chuyển cấu hình preset mã hóa video của FFmpeg từ `veryfast` sang `superfast`.
  - Giảm tải tính toán thuật toán nén phức tạp của CPU trên mỗi khung hình, rút ngắn tổng thời gian render video cuối cùng đi khoảng 15-30%.
  - Hoàn toàn an toàn cho phần cứng máy tính và chất lượng hình ảnh hiển thị không thay đổi.

## v1.1.7

### Highlights

- **Tối ưu tốc độ OCR trên CPU gấp 2 lần** (`frame_sampler.py`):
  - Giảm độ phân giải của frame ảnh chụp để đưa vào mô hình OCR từ `720p` (`min(720,iw)`) xuống `480p` (`min(480,iw)`).
  - Giúp giảm tới **55%** số lượng điểm ảnh (pixels) cần xử lý trên mỗi frame, giảm áp lực lên CPU đáng kể mà không ảnh hưởng tới độ chính xác của phụ đề chính.
  - Cập nhật hằng số ước tính thời gian chạy OCR từ `12s` xuống `7s` per frame (`douyin_reup_service.py`), giúp thời gian timeout tổng của video sát với thực tế chạy thực tế hơn.
  
## v1.1.6

### Highlights

- **Fix: Voice / Subtitle đồng bộ chính xác theo timestamp sub Trung gốc** (`douyin_render_pipeline.py`):
  - Bật `lock_subtitle_timing=True` trong `_generate_voiceover_from_srt` — voice giờ được đặt đúng vào khung giờ của từng dòng subtitle thay vì dồn liên tiếp vào nửa đầu video.
  - Trước đây: `_compose_timed_audio_sequence` compress tất cả gaps > 0.28s → voice kết thúc ở giây ~34 trong video 76s → 42s cuối im lặng hoàn toàn.
  - Sau khi sửa: silence thực sự được fill vào khoảng trống giữa các câu → người xem nghe voice đúng lúc cảnh nấu ăn tương ứng xuất hiện.

- **Fix: Timeout kill video dựa trên thời lượng video + fps OCR thay vì cứng** (`douyin_reup_service.py`):
  - Thêm hàm `_compute_item_timeout(video, settings)` tính timeout linh động: `min(240, duration × ocr_fps) × 12s + 600s`, lấy `max` với `batch_item_timeout_seconds` làm sàn tối thiểu.
  - Video 90s / 2fps → timeout tự động là 2760s (thay vì 2400s cứng → bị kill sai trước đây).
  - Video 120s / 2fps → 3480s; video 5 phút / 5fps → 3480s (capped 240 frames).
  - Video ngắn ≤ 60s vẫn dùng timeout mặc định 2400s bình thường.

- **Fix: Nền che subtitle (cover) vừa khít text thực tế, không còn che quá dày** (`subtitle_cover_detector.py`):
  - `pad_y` giờ tỷ lệ theo chiều cao **thực tế của text block** (`text_height × 35%`) thay vì cứng theo frame height (`frame × 2.5% = 32px`).
  - Sub 1 dòng (50px): nền che giảm từ **114px → 85px** (6.6% thay vì 8.9% frame).
  - Sub nhỏ (30px): giảm từ **94px → 51px** (4.0% thay vì 7.3%).
  - Giảm `min_height_ratio` mặc định từ `0.055` → `0.04` để tránh force-expand nền che khi text nhỏ.

## v1.1.5


### Highlights

- **Khắc phục triệt để lỗi tải video Douyin bằng CDP Network Interception**:
  - Tự động bắt URL stream CDN thực tế (`v*.douyinvod.com`) từ trình duyệt Chrome thông qua CDP Performance Logging khi phát video.
  - Bypass hoàn toàn API chi tiết của Douyin (`/aweme/v1/web/aweme/detail/`) - nơi thường xuyên chặn request thiếu chữ ký số (`_signature` / `X-Bogus`).
  - Giải quyết lỗi 52/176 video bị báo lỗi "Fresh cookies (not necessarily logged in) are needed".
  - Đảm bảo an toàn 100% cho tài khoản người dùng: Chỉ đọc log mạng nội bộ của Chrome, không thay đổi session hay cookies.

## v1.1.4

### Highlights

- **Đưa video vào lịch đăng Fleet trực tiếp từ tab Kết quả**:
  - Thêm nút **"Đưa vào Fleet"** xuất hiện ngay trên thanh header khi người dùng chọn ≥1 video hợp lệ trong tab Kết quả.
  - Modal chọn kênh hiện ra với danh sách kênh đã liên kết, tất cả được tích sẵn — người dùng chỉ cần bỏ tích những kênh không muốn đăng.
  - Sử dụng **caption, hashtag đã có sẵn từ pipeline reup** (lưu trong DB) thay vì template cứng — mỗi video có nội dung riêng biệt phù hợp với sản phẩm thực tế.
  - Tự động tìm link sản phẩm affiliate từ hashtags và tên file video.
  - Endpoint mới: `POST /api/fleet/queue/add-from-results`.

- **Phân trang danh sách hàng đợi Fleet**:
  - Danh sách Queue giờ hiển thị **10 video mỗi trang** thay vì render toàn bộ.
  - Thanh phân trang ở cuối danh sách hiển thị số trang hiện tại, tổng số video.
  - Nút điều hướng `← Trước` / `Tiếp →` tự động disable ở trang đầu/cuối.
  - Reset về trang 1 tự động khi dữ liệu được làm mới.

## v1.1.3

### Highlights

- **Video Aspect Ratio Optimization & Multi-Orientation Support**:
  - Defaulted all reup output videos to a vertical (9:16) format across both voiced (standard) and unvoiced (silent) pipelines.
  - Implemented automatic blurred background padding (`boxblur`) for aspect ratio mismatches, centering horizontal (16:9) and square (1:1) videos within the vertical canvas without cropping any visual content.
  - Added a new configuration option `video_dimension_mode` supporting four modes: "Dọc (9:16 - Mặc định)", "Ngang (16:9)", "Vuông (1:1)", and "Tự động (Theo video gốc)".
  - Built a dynamic visual layout simulator using pure CSS and detailed descriptive guides in Vietnamese directly in the reup settings card for a highly intuitive configuration experience.

## v1.1.2

### Highlights

- **Fix API Route Parameter Resolution**:
  - Fixed a critical bug in channel saving, product creation, and queue updates where FastAPI incorrectly interpreted the request body as query parameters. This was caused by local namespace imports inside `create_app()` failing to resolve under `from __future__ import annotations`.
  - Moved all Fleet Publisher schema imports to the module global level to ensure correct OpenAPI schema generation and body parsing.

## v1.0.64

### Highlights

- **Smart Chinese Subtitle Detection & Cover Logic Improvements**:
  - Automatically disabled subtitle cover (removed background box and blur) when no Chinese text (CJK) is detected in clean videos, keeping the visual presentation 100% clean and professional.
  - Falls back gracefully to manual/default subtitle positions for Vietnamese subtitles when covering is disabled.
  - Introduced an advanced **Gemini AI Vision Fallback** mechanism: when OCR positioning is uncertain (confidence is low or falls back to bottom), the system analyzes 3-4 key frames of the video via Gemini Vision to calculate precise vertical (Y) coordinates for the cover box, avoiding incorrect covering coordinates.
- **Enhanced Configuration & UI Controls**:
  - Added two new user-friendly toggle switches in Douyin Reup Advanced Settings: "Chỉ che khi thấy chữ Trung" (Only cover if Chinese detected) and "Gọi AI nếu vị trí không rõ" (Call Gemini Vision AI if position is unclear).
  - Designed all properties to be fully backwards-compatible.

### QA

- Verified all 6 subtitle cover detector tests pass.
- Verified 14 douyin render pipeline tests pass.
- Verified 9 douyin reup service tests pass.
- Verified 5 silent reup pipeline tests pass.


## v1.0.63

### Highlights

- **Subtitle Style Preview & Video Preview UI Fixes**:
  - Fixed the video preview box to render a completely transparent background when "Che phụ đề Trung" (subtitle cover) is disabled. This accurately represents how the final video is rendered without a cover and prevents drawing a fake dark slate box.
  - Implemented a repeating dark-mode checkerboard pattern (`repeating-conic-gradient`) for the style preview block when subtitle cover is disabled. This ensures both light-theme sub styles (dark text) and dark-theme sub styles (light text) are perfectly legible when previewing transparent backgrounds.
  - Restored full contrast and readability for light subtitle presets (such as "Sub nổi trên nền sáng") under all cover states.

### QA

- Verified frontend React components compile successfully.
- Verified visual preview state rendering logic for both enabled and disabled cover options.


## v1.0.62

### Highlights

- **Dynamic Subtitle Scanning & Flexible Positioning**: Removed strict bottom Y-limits, allowing subtitles located anywhere on the screen (including top or middle) to be scanned and covered out-of-the-box.
- **Smart Static Text Filtering**: Implemented a robust static text detection algorithm. Any Chinese text appearing in the same vertical coordinate across 28%+ of frames (e.g. static brand logos, watermarks, product packaging labels) is automatically filtered out, ensuring it is never covered by mistake.
- **Optimized Advanced Settings out-of-the-box**: Refined default settings to be the most optimal and stable for users:
  - Changed default ASR model size to `"base"` for extremely fast CPU/GPU transcription.
  - Disabled subprocess isolation by default for both ASR and OCR, enabling instant model caching and a 45x speedup for batch processing.
  - Set default OCR region mode to `"full_frame"` to support scanning the entire video screen automatically.
- **Enhanced Middle-Screen Subtitle Detection**: Allowed two-line subtitles in the middle/upper screen by expanding the height ratio limit to 0.11 while maintaining strict horizontal centrality requirements.

### QA

- Verified all 6 subtitle cover detector tests pass, including a new test for static text filtering.
- Verified schema and frontend default configurations are fully aligned.
- Verified backend compilation and syntax check passed.


## v1.0.61

### Highlights

- Optimized CPU ASR performance by automatically disabling subprocess isolation when running ASR on CPU. This allows the parent process to load and cache the Whisper model in memory once, speeding up subsequent batch video transcriptions by 45x (transcription takes 2-5 seconds instead of 7-8 minutes per video).
- Fixed smart subtitle cover positioning from drawing giant cover boxes over products. Enforced a vertical threshold (bottom ratio >= 0.68) to completely filter out Chinese characters printed on products, faces, or background elements in the middle/upper parts of the screen, focusing only on real bottom subtitles.

### QA

- Verified ASR subprocess isolation is disabled on CPU to enable model caching.
- Verified subtitle cover detector filters out CJK blocks in the middle and upper screen (Y < 68% of screen height).
- Backend build and syntax checks passed.


## v1.0.60

### Highlights

- Added proactive ASR health check on batch job initialization to automatically optimize settings (switches GPU/CUDA to CPU or falls back to OCR if ASR is completely broken).
- Fixed subprocess isolation for ASR GPU-to-CPU fallback so subsequent batch videos skip GPU checks immediately after a failure, avoiding timeout delays.
- Added Ultimate Fallbacks in subtitle source detection to guarantee both OCR and ASR are tried before failing any video.
- Fixed subtitle cover and background position not updating during manual review re-renders by preserving `ocr_debug_json_path` in document context.
- Untracked local junk files (*.log, *.db, .cache/) and hardened `.gitignore` for a cleaner repository.

### QA

- Verified ASR proactive check and CUDA fallback on CPU.
- Verified Ultimate Fallback triggers OCR on mock failures.
- Backend build and syntax checks passed.


## v1.0.59

### Highlights

- Added a shared ASR/OCR subtitle quality gate so noisy lines such as `Giảm cân`, `Đi, đi, đi`, and `《Phim》` are rejected before translation/rendering.
- Moved subtitle source priority to safer ordering: sidecar, embedded subtitle, OCR if quality passes, ASR if quality passes, otherwise `music_only_safe`.
- Hardened ASR against music/noise hallucination with no-speech, log-probability, compression-ratio, VAD, and segment-level filters.
- Made Silent Mode conservative by default: no generated Vietnamese captions or voiceover unless OCR, product detection, and visual context are reliable enough.
- Added subtitle content quality metadata to output logs/reports, including rejected sources, reasons, score, stats, and fallback mode.
- Fixed a circular import that could break standalone batch stress checks.

### QA

- Backend test suite passed: `540 passed`.
- Frontend production build passed.

## v1.0.58

### Highlights

- Added a safe music-only fallback for Silent Mode when OCR/caption/product context is too short, noisy, or unsafe for Vietnamese subtitle and voiceover generation.
- Kept Silent Mode voiceover aligned to the subtitle timeline when voiceover is allowed, and stopped generating voice when estimated narration would be too long for the video.
- Standardized Silent Mode output MP4 names such as `video_001_silent.mp4` instead of using long Douyin/Chinese source names.
- Replaced original video audio when a Silent Mode BGM source is configured, avoiding harsh original-audio-plus-background-music mixing.
- Added hard per-video worker timeouts for default Douyin Reup batches so one stuck OCR/ASR/subtitle-source item cannot freeze a large batch for hours.
- Removed the generated product-name colon prefix from Silent Mode captions.

### QA

- Silent pipeline, Douyin routing, silent render job, silent review, Douyin render, and queue watchdog regression tests passed.
- Frontend production build passed.

## v1.0.57

### Highlights

- Added safe post-render cleanup for Douyin Reup and Silent Mode outputs: final MP4, subtitles, logs, QA report, product context, and publish manifest are kept while heavy temporary frames/crops/source copies/audio intermediates are removed after successful renders.
- Added `publish_manifest.json` per successful output so future auto-posting, scheduling, captions, and comment workflows can still use the processed video context after cleanup.
- Added a Vietnamese "Dọn file tạm sau xử lý" control in the Reup workflow, plus per-video cleanup status in result cards.
- Skips cleanup automatically when final QA fails or when the user enables keeping temporary files for debugging.

### QA

- Added backend coverage for cleanup deletion safety, keep-temp mode, and QA-failed skip behavior.
- Douyin Reup, Silent Mode, Douyin API regression tests passed.
- Frontend production build passed.

## v1.0.56

### Highlights

- Fixed Silent Mode AI vision on Windows by writing internal analysis frames with stable ASCII filenames and Unicode-safe image encoding.
- Restored Gemini vision product detection for Douyin videos with Chinese/emoji filenames, including frame and focus-crop evidence in product reports.
- Filtered ASR credit/watermark text such as `字幕by...` so silent product videos are not routed into the voice reup flow by mistake.
- Reduced false `overlay_missing` QA warnings when overlay mode is disabled, while keeping final MP4 validation in the silent render path.

### QA

- Silent product detector, visual frame analyzer, silent render pipeline, speech detector, Douyin routing, and final output QA tests passed.
- Verified against the real test batch that new frame paths exist and are passed into AI vision.
- Frontend production build passed.

## v1.0.55

### Highlights

- Hardened Silent Mode speech detection so audio energy alone no longer pushes product-only videos into the voice reup flow.
- Added automatic short ASR confirmation for suspicious audio before treating a silent-mode video as spoken content.
- Kept music, ambient sound, and operation-noise videos in Silent Mode when ASR finds no clear speech segments or cannot run safely.

### QA

- Speech detector and Douyin silent/voice routing tests passed.
- Silent product detector, silent pipeline, and silent review tests passed.

## v1.0.54

### Highlights

- Upgraded Silent Mode product recognition with Gemini vision frames, crop evidence, candidate voting, and fallback context for videos without text/subtitles.
- Added product detection details to silent output cards and preserved that context when rendering approved review documents.
- Fixed Douyin result selection so failed or not-yet-rendered videos can still be selected for "Chọn sửa lại" and rerendered from the adjust flow.
- Kept export selection separate from rerender selection so broken outputs are not accidentally included in export packs.

### QA

- Frontend production build passed.
- Douyin retry, preset retry, silent review, silent pipeline, and silent product detector tests passed.

## v1.0.53

### Highlights

- Fixed Gemini API key multi-line input so pressing Enter keeps the new line while adding keys.
- Improved Silent Mode defaults so Douyin Reup can auto-detect product context instead of locking every batch to a generic product label.
- Reduced watermark/platform noise in silent keyword tagging while preserving useful product hashtags.
- Simplified Douyin Reup result pages by hiding duplicated content/QA review actions and keeping rerender actions in the result flow.

### QA

- Frontend production build passed.
- Silent/reup backend regression tests passed.

## v1.0.52

### Highlights

- Hardened the Windows release build against temporary FFmpeg/Piper download failures by retrying incomplete downloads.
- Updated the release workflow actions to current Node-runtime-compatible major versions.

### QA

- Frontend production build passed.
- PowerShell release script syntax check passed.

## v1.0.51

### Highlights

- Fixed Light theme readability across notice cards, guidance cards, status panels, toast notifications, and common action blocks.
- Made Douyin Reup result pages denser with a 2/3/4-column video grid and pagination instead of showing every output at once.
- Changed Gemini API key settings to a multi-line input so users can paste one key per line.
- Reworded technical labels such as Backend, Final QA, Export Pack, Retry, Log, and output into clearer Vietnamese UI copy.
- Removed internal silent-reup routing codes from visible user guidance.

### QA

- Frontend production build passed.
- Manually checked Light theme pages for remaining large dark-theme blocks.

## v1.0.50

### Highlights

- Refined Light theme colors so tab bars, cards, active states, and action buttons no longer reuse the heavy dark-theme cyan treatment.
- Added theme-aware accent tokens for primary buttons, soft active backgrounds, accent text, and readable button foreground text.
- Restyled shared tabs to use a soft active chip in Light/Custom themes instead of a solid dark-blue block.
- Improved Light theme success, warning, and error colors so status badges remain readable on bright backgrounds.

### QA

- Frontend production build passed.

## v1.0.49

### Highlights

- Added Light, Dark, and Custom theme modes in Settings > Giao diện & Theme.
- Added custom colors for background, primary text, muted text, cards, borders, and accent/buttons.
- Added custom app background images from either a local image picker or an image URL.
- Added background controls for image visibility, blur, and readability overlay, with preview/save behavior persisted locally.

### QA

- Frontend production build passed.
- Verified the Settings route responds successfully from the Vite dev server.

## v1.0.48

### Highlights

- Restyled the Douyin Reup result retry panel to match the dark desktop UI instead of showing a bright, confusing block.
- Made "Render lại đã chọn" the primary action, with the selected video count shown clearly before rerendering.
- Split retry loading from the main page loading state so selected rendered videos are not blocked from being queued again.
- Kept "Chạy tiếp phần còn lại", "Chọn lỗi/QA fail", and "Bỏ chọn" as secondary actions for a simpler recovery flow.

### QA

- Frontend production build passed.

## v1.0.47

### Highlights

- Added a visible "Chỉnh/render lại" action directly on the `/results/...` page for Douyin Reup jobs.
- Added a side-panel guide on result pages so users can select bad-position subtitle videos, reopen the old batch settings, and render only the selected videos.
- Preserves selected result videos through the reopen flow, so the Douyin Reup page preselects them and shows the "Render lại đã chọn" action immediately.

### QA

- Frontend production build passed.

## v1.0.46

### Highlights

- Added a stopped-batch recovery flow from the render queue back into Douyin Reup so users can adjust settings, then continue the unfinished videos or render selected outputs again.
- Added clear retry modes: "Chỉ dựng lại video", "Đọc lại chữ trên video rồi dựng", and "Làm lại phụ đề/thoại rồi dựng" instead of exposing OCR-step wording.
- Fixed retry cache behavior so render-only reuses existing subtitles, while the read-screen-text mode reruns subtitle detection/OCR and translation before rendering.
- Kept the mid-screen Chinese subtitle cover/OCR improvements in the release, including automatic cover probing for videos with visible hard-sub text.

### QA

- Focused backend retry/OCR-cover tests passed.
- Frontend production build passed.

## v1.0.45

### Highlights

- Added global toast notifications so actions across the app show visible feedback instead of quiet in-page messages that are easy to miss.
- Hardened large Douyin/reup render queues against temporary Windows file locks when saving queue state.
- Fixed failed queue bookkeeping so a single scheduler/state error no longer marks every pending video as failed.
- Improved Recovery Center counts by reading the real queue state, allowing interrupted batches to resume the remaining videos.
- Increased subtitle timing guard write retries to reduce one-off SRT failures caused by temporary file locks.

### QA

- Backend compile check passed for the queue, recovery, API, and subtitle timing modules.
- Frontend production build passed.
- Verified the real failed batch is detected as 10 completed, 1 failed, and 1572 resumable items instead of 1583 failed items.

## v1.0.44

### Highlights

- Fixed the Douyin download link list so it no longer grows past the right-side download card when many links are loaded.
- The link list now measures the right panel height and scrolls inside its own box, keeping both desktop columns aligned.

### QA

- Frontend production build passed.

## v1.0.43

### Highlights

- Replaced the Vietnamese subtitle style presets with eight practical Vietnamese-friendly options for basic readability, TikTok yellow, modern clean, sale red, skincare pink, tech blue, food yellow-orange, and bright-background subtitles.
- Matched each preset to the requested text color, cover background color/opacity, stroke color, and shadow opacity.
- Clarified in the UI that selected subtitle presets and manual style tweaks are saved automatically for future sessions.

### QA

- Verified all eight subtitle presets against the requested color table.
- Frontend production build passed.

## v1.0.42

### Highlights

- Fixed the Douyin download page so the scanned link list fills the available space instead of leaving a large blank area below the rows.
- Let the manual link input expand in the same panel layout for a cleaner desktop experience.

### QA

- Frontend production build passed.

## v1.0.41

### Highlights

- Added automatic OCR watermark/channel-name detection across repeated frames, so users no longer need to type watermark text for large batches.
- Kept common watermark terms built into the backend while allowing optional manual terms only for rare edge cases.
- Simplified the OCR settings UI: watermark filtering is automatic by default, and the manual keyword box is tucked into an advanced detail section.
- Improved OCR debug summaries with auto-detected watermark term counts.

### QA

- Focused OCR/Douyin backend tests passed for watermark filtering, OCR fallback, one-click batch, and service flow.
- Frontend production build passed.

## v1.0.40

### Highlights

- Improved Vietnamese subtitle display so each cue prefers one complete sentence instead of chopped fragments.
- Limited subtitle display to a maximum of two lines when the sentence can fit, with soft splitting only for unusually long sentences.
- Added punctuation safeguards so merged Vietnamese subtitle/voiceover text no longer runs two sentences together without a period.
- Applied the same sentence-first behavior across fixed SRT, voice-synced SRT, and rendered ASS subtitles.

### QA

- Focused backend tests passed for subtitle timing, ASS rendering, voice subtitle sync, Douyin render pipeline, one-click batch, service flow, and subtitle translation.
- Verified against a real tested output subtitle file that the generated SRT/ASS keeps complete sentences with at most two display lines.

## v1.0.39

### Highlights

- Prevented repeated hidden Auto Tool instances by reusing the running server and guarding startup with an instance lock.
- Let the launcher fall back to a free local port when `8000` is occupied by another app, so non-technical users can still open the tool normally.
- Improved Douyin Reup OCR so one-click runs carry OCR region settings and weak bottom/middle subtitle scans automatically retry the full video frame.
- Refined the desktop Douyin Reup start screen to make review, tuning, and final MP4 render actions clearer for Vietnamese users.

### QA

- Focused backend tests passed for launcher, OCR fallback, subtitle source detection, Douyin one-click, presets, and render flow.
- Frontend production build passed.

## v1.0.29

### Highlights

- Added quick Vietnamese subtitle style templates for review, reup, sale, beauty, tech, and minimal product videos.
- Subtitle style templates now apply text color, cover background, stroke, shadow, font size, line length, and cover thickness in one click.
- Removed the duplicate advanced settings button from the Douyin Reup side panel.
- Fixed advanced settings drawer scrolling so the page behind stays locked and only the drawer content scrolls.

### QA

- Frontend production build passed.
- Browser verification passed on `/douyin-reup`: one advanced settings button, six subtitle templates visible, template selection updates style controls, drawer scroll is isolated.

## v1.0.28

### Highlights

- Fixed automatic updater scripts waiting forever when another `AutoTool.exe` instance is open or the user manually reopens the app.
- Updater scripts now wait for the exact current process PID instead of every process named `AutoTool.exe`.
- Recovered the local install flow after the v1.0.27 update package was downloaded but left waiting in `_update`.

### QA

- Updater unit tests and frontend build passed.
- Local install was manually recovered from the stuck v1.0.27 updater and verified through `/api/health` before publishing this fix.

## v1.0.27

### Highlights

- Fixed smart subtitle cover choosing noisy mid-frame OCR blocks instead of the real lower Chinese subtitle lane.
- Added a thin bottom fallback when OCR coordinates are low-confidence or fragmented, avoiding oversized floating cover blocks.
- Made Vietnamese subtitle text split across the same timed cover intervals so text and background move together.
- Widened smart cover rectangles so Vietnamese text no longer overflows the background.
- Lowered the default fallback cover height from 22% to 12% for less intrusive bottom coverage.

### QA

- Backend test suite passed: 474 tests.
- Frontend production build passed.
- Verified the noisy real-world OCR debug from video_020 now resolves to a thin bottom fallback instead of mid-frame segments.

## v1.0.26

### Highlights

- Added custom Vietnamese subtitle style controls for font, size, text color, stroke, shadow, wrapping and max lines.
- Applied custom subtitle style overrides during Douyin render so exported ASS subtitles follow the UI settings.
- Started the Windows one-click backend as a hidden process with separate launcher, server app, stdout and stderr logs.
- Hid backend child processes such as FFmpeg, ffprobe, Piper and dependency checks to avoid repeated terminal flashes.
- Kept desktop folder/file open actions visible while making background processing no-console friendly.

### QA

- Backend test suite passed: 472 tests.
- Frontend production build passed.
- Windows launcher hidden-start smoke test passed: health OK, shutdown OK, no terminal/file-lock loop.

## v1.0.25

### Highlights

- Made smart subtitle cover use OCR block timestamps to draw dynamic cover regions instead of one oversized global band.
- Tightened Chinese subtitle detection around real OCR text boxes and filtered lower-frame subtitle-like clusters.
- Raised quick subtitle-position probe to 1 FPS by default so short videos get per-second position checks.
- Allowed thinner fallback cover height for cases where auto-position is not available.

### QA

- Focused backend subtitle cover/render pipeline tests passed.
- Frontend production build passed.

## v1.0.11

### Highlights

- Added large-batch reliability controls for Douyin voice, Silent Reup and product/affiliate render flows.
- Added queue chunk planning, batch chunk logs and periodic memory cleanup between chunks.
- Added queue watchdog detection for stale running items, exposed through queue/resource APIs.
- Added configurable FFmpeg timeout per queued item and ASR audio cap per reup settings.
- Added automatic pause after repeated consecutive video failures to avoid wasting overnight batches.
- Added frontend "Hiệu năng và chống kẹt" controls for safe/balanced/fast batch modes.
- Fixed a queue/job-recovery circular import by lazy-loading `JobResumeService`.

### QA

- Backend test suite passed: 432 tests.
- Frontend production build passed.

## v1.0.10

### Highlights

- Added resource-aware batch planning, stage gates and safer product render worker limits.
- Improved Douyin/Silent job resume so interrupted, pending and failed items can continue more reliably.
- Preserved Google Cloud TTS credentials when reup voiceover overrides provider/voice.
- Added startup readiness checks for required Gemini/TTS/BGM config before long reup batches.
- Added mixed-batch auto routing: Silent batches can route speech videos to voice reup, and voice batches can route no-speech videos to Silent Mode when safe.
- Made required subtitle QA failures explicit instead of warning-only.
- Capped ASR audio duration with `AUTO_TOOL_ASR_MAX_AUDIO_SECONDS` to reduce long-video hangs.
- Hardened job logging when background workers start before the SQLite log table is initialized.

### QA

- Backend test suite passed: 428 tests.
- Frontend production build passed.

## v1.0.6

### Highlights

- Fixed Douyin Reup jobs appearing stuck at 10% while frontend polling still returned HTTP 200.
- Made Fast Auto actually faster by using the tiny ASR model, VAD, lower OCR sampling and cached OCR/ASR models.
- Optimized hard-sub OCR frame sampling and batched EasyOCR recognition.
- Disabled hidden heavy ASR speech detection in Silent Mode unless explicitly enabled.
- Added detailed backend progress stages, FFmpeg timeout handling and frontend stale-worker warnings.
- Rebuilt Windows local app package with bundled FFmpeg, Piper TTS and Vietnamese Piper model.

### QA

- Backend focused test suite passed.
- Frontend production build passed.
- Windows EXE smoke test passed: /api/health returned version 1.0.6 and frontend / returned HTTP 200.

## Silent / Immersive Product Reup v1.0.0-rc1

### Highlights

- Silent detection, visual segmentation and hard-sub OCR integration
- Industry caption templates and lightweight visual tagging
- Segment tag editor and caption regeneration without re-analysis
- Subtitle review, corrected SRT/ASS and optional Vietnamese voiceover
- Overlay/subtitle rendering, BGM mixing and original-audio retention
- Final Output QA, Export Pack and per-video failure isolation
- Standardized RC job, video, caption and visual-tag logs

### What This Version Does Not Do

- Does not download videos, remove watermark/hardcoded text, auto login or auto post
- Does not use heavy AI vision/object detection by default

### Recommended Workflow

Start with Silent Chill Immersive and 3-5 authorized local videos. Review tags/captions, render one video, inspect Final QA, then scale the batch.

### Known Limitations

- Visual tagging is rule-based and captions are more generic without product context.
- OCR accuracy drops for small, blurry, animated text or complex backgrounds.
- Users must review captions and ensure rights to source videos, music and assets.

### QA Status

Automated backend/API/build QA is included. Final release still requires the real-video checklist and no open release blocker.

---

## Highlights

- Folder-based Douyin video processing
- Chinese ASR to Vietnamese subtitle
- Hard-sub Chinese OCR fallback
- Subtitle translation and review
- Subtitle quality scoring
- Safe rewrite suggestions
- Overlay/subtitle style rendering
- Background music mixing
- Final output QA
- Platform export pack

## What This Version Does Not Do

- Does not download videos automatically
- Does not remove watermark
- Does not auto post
- Does not bypass platform restrictions

## Recommended Workflow

Use Safe Review preset for first runs:

1. Test with 3-5 videos first.
2. Check subtitle review documents.
3. Render one approved video.
4. Read Final QA warnings.
5. Create Export Pack only after reviewing output manually.

## Known Limitations

- Tool does not download Douyin videos.
- Tool does not remove watermark or hard-sub Chinese text from the video image.
- ASR can be inaccurate when audio is noisy or speech is quiet.
- OCR can be inaccurate when text is small, blurry, animated, or on a complex background.
- Automatic translation should be reviewed by the user before posting.
- Final QA is rule-based technical validation, not a replacement for watching the final video.
- Users must ensure they have the right to use source videos, music, and other assets.

## Upgrade Notes

- `VERSION` is now `1.0.0-rc1`.
- `/api/health` reports the release-candidate version.
- Use `examples/douyin_reup_v1_rc/` for RC validation configs and QA templates.

## QA Status

Release candidate is ready for local QA with the RC test pack. Final release requires passing the manual QA checklist and no open release blockers.
