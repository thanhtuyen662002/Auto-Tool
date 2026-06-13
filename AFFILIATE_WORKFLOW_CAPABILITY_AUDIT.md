# Báo cáo Đánh giá Năng lực Affiliate Workflow (Affiliate Workflow Capability Audit)

**Dự án:** Auto Tool Studio  
**Mục tiêu:** Kiểm tra chuyên sâu năng lực thực tế của luồng công việc *Product Video Builder / Affiliate Video* để xác định khả năng hỗ trợ, pipeline sử dụng, các module hoạt động, và khuyến nghị hướng phát triển.

---

## 1. Tổng quan Năng lực thực tế (Workflow Capability Overview)

Workflow Affiliate (**Product Video Builder**) hiện tại là một luồng xử lý hoàn chỉnh (End-to-End) có mức độ tự động hóa và thông minh cao, hoạt động độc lập với các luồng Douyin Reup và Silent Mode. Trọng tâm của workflow này là chuyển đổi thông tin sản phẩm bán hàng (từ Shopee/TikTok Shop) cùng với các video tư liệu thô thành hàng loạt video quảng cáo/review sản phẩm tự động, có giọng lồng tiếng, phụ đề hiệu ứng chất lượng cao, nhạc nền và hình ảnh nhận diện thương hiệu.

---

## 2. Đánh giá Khả năng Nhập liệu (Input Capability Audit)

### 2.1. Nhập thông tin sản phẩm (Product Data)

Hệ thống xử lý thông tin sản phẩm được điều phối thông qua [ProductImportService](file:///d:/Projects/Auto-Tool/backend/app/modules/product_import/product_import_service.py) và [ProductParser](file:///d:/Projects/Auto-Tool/backend/app/modules/product_import/product_parser.py). Các kênh nhập dữ liệu sản phẩm bao gồm:

*   **Manual Product Input: SUPPORTED**  
    Người dùng có thể tự điền thông tin sản phẩm trực tiếp thông qua form giao diện (`ProductInfoForm`) hoặc dán văn bản thô. Hệ thống sẽ tự động phân tích cấu trúc văn bản thô qua `ProductParser._parse_text()` để tách biệt: Tên sản phẩm, Thương hiệu, Mô tả, Tính năng chính, và CTA.
*   **Shopee Extension Data: SUPPORTED**  
    Hỗ trợ trọn vẹn việc nhận dữ liệu cấu trúc (structured payload) gửi về từ Chrome Extension thông qua API. Tệp `ProductParser._parse_shopee_extension()` chịu trách nhiệm phân tích sâu thông tin giá bán, giá gốc, tỷ lệ giảm giá, lượt bán, đánh giá sao, địa chỉ shop, và các biến thể phân loại sản phẩm.
*   **Import Inbox Data: SUPPORTED**  
    Hòm thư Inbox (`ImportInboxPage`) lưu trữ và quản lý toàn bộ các bản nháp sản phẩm trích xuất từ SQLite. Người dùng có thể chỉnh sửa bản nháp, duyệt thông tin, tải hình ảnh và tạo nhanh dự án từ các bản nháp này thông qua `ProductDraftService`.
*   **JSON Import: SUPPORTED**  
    Cho phép import trực tiếp cấu hình sản phẩm từ tệp tin JSON thông qua `ProductParser._parse_json()`. Tự động nhận diện bí danh trường thông tin (`name`, `brand`, `desc`, `benefits`, `specs`, v.v.).
*   **CSV Import: PARTIALLY SUPPORTED**  
    Hỗ trợ import từ tệp CSV qua `ProductParser._parse_csv()`. Tuy nhiên, hiện tại hệ thống chỉ đọc và xử lý dòng dữ liệu sản phẩm đầu tiên trong tệp CSV (có cảnh báo đi kèm).

### 2.2. Xử lý video tư liệu gốc (Source Videos)

*   **1 Video: SUPPORTED**  
    Hệ thống quét, phân mảnh (segmentation) và chấm điểm một video bình thường.
*   **Nhiều Video: SUPPORTED**  
    Quét toàn bộ danh sách tệp video trong thư mục nguồn và phân mảnh chúng đồng thời.
*   **Thư mục Video (Folder Video): SUPPORTED**  
    Hệ thống làm việc trực tiếp dựa trên đường dẫn thư mục nguồn máy tính (`source_folder`).
*   **Nguồn hỗn hợp (Mixed Sources): PARTIALLY SUPPORTED**  
    Hỗ trợ nhiều định dạng video khác nhau (mp4, mkv, avi, v.v.) trong cùng thư mục nguồn, nhưng bắt buộc toàn bộ video đầu vào phải nằm chung trong **một thư mục duy nhất**. Không hỗ trợ thêm nhiều đường dẫn thư mục khác nhau.
*   **Giới hạn hiện tại:**
    *   Quá trình quét và phân cảnh (segmentation) có thể trở nên rất chậm khi số lượng video đầu vào trong thư mục quá nhiều.
    *   Hệ thống có giới hạn số lần lặp tìm kiếm segment an toàn `max(1000, len(segments) * len(slots) * 10)` tại `ProductTimelineBuilder` để ngăn ngừa tình trạng treo/đứng luồng khi không tìm thấy đủ cảnh quay phù hợp với tiêu chí slot.

### 2.3. Khả năng tích hợp Tài nguyên (Assets)

*   **Music: SUPPORTED**  
    Hỗ trợ chèn nhạc nền tự động từ thư mục chỉ định, cấu hình âm lượng, fade-in/fade-out, và đặc biệt là cơ chế **Sidechain Compression (Ducking)** tự động giảm âm lượng nhạc nền dưới giọng nói.
*   **Voice & TTS: SUPPORTED**  
    Tự sinh giọng đọc thuyết minh thuyết phục bằng trí tuệ nhân tạo thông qua `VoiceGenerator`.
*   **TTS Engines: SUPPORTED**  
    Tích hợp đa dạng nhà cung cấp qua `TTSManager`: Edge TTS (miễn phí, chất lượng cao), Google Cloud TTS, GTTS, và Piper TTS (tạo giọng nói offline nội bộ, siêu nhanh).
*   **Overlay: SUPPORTED**  
    Hỗ trợ đè ảnh phủ trang trí (Preset overlay hoặc Custom overlay do người dùng thiết kế) giúp đồng bộ khung nhận diện thương hiệu.
*   **Subtitle: SUPPORTED**  
    Tự động đồng bộ và sinh phụ đề định dạng SRT cùng phụ đề ASS có thiết kế đồ họa cao cấp, burn-in trực tiếp vào video thông qua FFmpeg.
*   **Images: NOT SUPPORTED**  
    Hệ thống **không hỗ trợ** import ảnh tĩnh làm cảnh quay/clip trên timeline dựng video. Ảnh tĩnh chỉ được hỗ trợ để chèn đè làm logo/khung Overlay trang trí.
*   **Logo / CTA: SUPPORTED**  
    Logo được gắn thông qua overlay. Lời kêu gọi hành động (CTA) được chèn cố định ở cảnh cuối cùng dựa vào kịch bản và template của timeline.

---

## 3. Hệ thống Quản lý Dự án (Project System Audit)

*   **Create Project: WORKING**  
    Khởi tạo dự án thông suốt từ Inbox bản nháp (`create_project_from_draft`) hoặc form tạo trực tiếp, tự động ánh xạ các thiết lập preset ngành hàng thích hợp.
*   **Edit Project: WORKING**  
    Cho phép chỉnh sửa toàn bộ cấu hình dự án thông qua giao diện React (`RenderSettingsPage`), hỗ trợ lưu cấu hình dự án xuống file `project_config.json` và SQLite.
*   **Duplicate Project: MISSING**  
    Không có tính năng nhân bản dự án (Duplicate) trên giao diện lẫn API. Muốn nhân bản người dùng phải tạo mới từ đầu.
*   **Save Draft / Resume Draft: WORKING**  
    Cơ chế tự động lưu bản nháp hoạt động tốt. Người dùng có thể quay lại sửa đổi bất kỳ dự án nào chưa render.
*   **Delete Project: WORKING**  
    Hỗ trợ xóa hoàn toàn dự án, dọn dẹp các tệp tạm và thông tin lưu trữ trong DB.
*   **Export Project: WORKING**  
    Hỗ trợ xuất bản thư mục kết quả (Export Pack) chứa video hoàn chỉnh, file phụ đề SRT/ASS độc lập, kịch bản, hashtags, và thông tin đăng tải.

---

## 4. Kiểm tra năng lực dòng thời gian (Timeline Capability Audit)

Quy trình dựng dòng thời gian được xử lý tự động bởi [ProductTimelineBuilder](file:///d:/Projects/Auto-Tool/backend/app/modules/timeline_templates/product_timeline_builder.py).

*   **Timeline Builder: WORKING**  
    Dựng dòng thời gian tự động dựa trên cấu trúc slot của các mẫu dựng (Timeline Templates).
*   **Segment Builder & Scene Builder: WORKING**  
    Tách video nguồn thành các phân cảnh thô dựa trên cường độ cắt (`cut_intensity`) và ánh xạ chúng vào các slot thích hợp trên timeline.
*   **Có Timeline động không? YES**  
    Thời lượng từng clip trên timeline có khả năng **co giãn động** (speed up/down) tùy thuộc vào độ dài câu thuyết minh nói ở cảnh đó (TTS duration) và thiết lập tốc độ biến thiên nhằm đảm bảo video khớp âm thanh hoàn hảo.
*   **Có Timeline nhiều video không? YES**  
    Hệ thống có thuật toán đa dạng nguồn cảnh quay (`_source_diversity_score`), ưu tiên chọn các clip từ các video nguồn khác nhau để đảm bảo thành phẩm sinh động, không bị trùng lặp liên tục từ một source.
*   **Có reorder scene không? NO**  
    Không hỗ trợ tính năng kéo thả thay đổi thứ tự các cảnh trên giao diện UI. Thứ tự các slot (ví dụ: Hook -> Product -> Demo -> Benefit -> CTA) là cố định theo cấu trúc Timeline Template đã chọn.
*   **Có scene duration không? YES**  
    Có kiểm soát thời lượng tối thiểu/tối đa cho từng clip (`min_clip_duration`, `max_clip_duration`) và tự động co giãn bằng tham số tốc độ của FFmpeg.

---

## 5. Kiểm tra năng lực kịch bản (Script Capability Audit)

Hệ thống kịch bản được vận hành bởi [ScriptWriter](file:///d:/Projects/Auto-Tool/backend/app/modules/script_writer/script_writer.py) và [ScriptVariantGenerator](file:///d:/Projects/Auto-Tool/backend/app/modules/script_variants/script_variant_generator.py).

*   **Có AI Script không? YES**  
    Tích hợp trực tiếp API Gemini (mặc định: `gemini-3.1-flash-lite`) để tự động tạo kịch bản từ thông tin sản phẩm và tone giọng mong muốn.
*   **Có manual script không? YES**  
    Người dùng có thể viết tay toàn bộ kịch bản hoặc chỉnh sửa trực tiếp nội dung từng câu thuyết minh trên bảng điều khiển giao diện trước khi render.
*   **Có hybrid script không? YES**  
    Hệ thống hỗ trợ tạo kịch bản nháp hàng loạt bằng AI (Gemini), sau đó cho phép người dùng mở Editor để chỉnh sửa thủ công từng dòng thuyết minh và duyệt (approve) trước khi thực hiện kết xuất.

---

## 6. Sức khỏe và Độ tương thích Tính năng hiện đại (Modern Features Compatibility Audit)

*   **Smart Segment Scoring: YES**  
    Đang sử dụng module `SegmentScorer` chấm điểm chất lượng cảnh quay dựa trên Computer Vision (brightness, sharpness, motion, stability, freeze).
*   **Product-aware Timeline Templates: YES**  
    Tích hợp 4 mẫu dựng chuyên nghiệp (`product_showcase_clean`, `ugc_reviewer_natural`, `fast_tiktok_recut`, `problem_solution`) với cơ chế lọc tag và boost điểm thông minh.
*   **Script Variant Generator: YES**  
    Sử dụng Gemini sinh 6 biến thể kịch bản khác nhau (`problem_hook`, `reviewer_natural`, `benefit_first`, `use_case_scene`, `fast_sales`, `comparison_soft`).
*   **Subtitle Translation Engine: NO (NOT APPLICABLE)**  
    Không sử dụng. Khác với Douyin Reup dịch phụ đề Trung -> Việt, luồng Affiliate sinh kịch bản tiếng Việt trực tiếp từ dữ liệu sản phẩm nên không cần dịch thuật.
*   **TTS Engine: YES**  
    Sử dụng module TTS lồng tiếng và tự động tạo trục thời gian khớp thoại (`build_subtitle_timeline`).
*   **Source Media Browser: YES**  
    Người dùng có thể review và phân loại video/segment (favorite/good/excluded) từ giao diện, hệ thống sẽ tự động cập nhật SQLite và áp dụng boost điểm/loại trừ cảnh khi dựng timeline.
*   **Queue Control: YES**  
    Tích hợp đầy đủ cơ chế kiểm soát hàng đợi (`QueueStateService`), cho phép Pause, Resume, Cancel trong quá trình render hàng loạt.
*   **Crash Recovery: YES**  
    Hỗ trợ ghi nhận checkpoints và khôi phục job thông qua `JobRecoveryService` khi hệ thống xảy ra sự cố đột ngột.

---

## 7. Chấm điểm Sức khỏe Luồng công việc (Workflow Health Score)

Dựa trên kết quả khảo sát thực tế của hệ thống, luồng công việc Affiliate đạt điểm sức khỏe như sau:

| Thành phần | Điểm số (0-100) | Đánh giá & Ghi chú |
|------------|-----------------|--------------------|
| **UI** | **92** | Trực quan, đồng bộ glassmorphic, đầy đủ tính năng cấu hình. Điểm trừ: chưa có editor kéo thả timeline trực quan. |
| **Backend** | **95** | Rất ổn định, kiến trúc module hóa sạch sẽ, quản lý SQLite chặt chẽ. |
| **Pipeline** | **95** | Sự phối hợp giữa TTS, Sidechain Audio Mix, và ASS Subtitles hoạt động đồng bộ và mượt mà. |
| **Render** | **90** | FFmpeg thực thi chính xác, ổn định. Điểm trừ: chưa hỗ trợ ảnh tĩnh làm source clip. |
| **Assets** | **90** | Hỗ trợ nhiều TTS provider, custom overlays và ASS subtitle chất lượng cao. |
| **Project System** | **85** | Quản lý dự án đầy đủ. Điểm trừ: thiếu nút Duplicate nhanh dự án. |
| **Modern Features**| **92** | Đã tích hợp đầy đủ hầu hết các cấu phần thông minh (AI Variant, Segment Scoring, Queue, Recovery). |

---

## 8. Khuyến nghị và Kết luận (Executive Conclusion)

1.  **Năng lực hiện tại của Workflow Affiliate:** **Cực kỳ mạnh mẽ**. Nó không chỉ là một workflow thô sơ mà đã có sự tham gia của AI (Gemini sinh kịch bản biến thể), Computer Vision (quét và chấm điểm chất lượng cảnh quay) và Audio Processing chuyên nghiệp (Sidechain compression/ducking).
2.  **Pipeline sử dụng:** Đang sử dụng pipeline kết xuất **mới và tối ưu** (`render_worker.py` điều phối, `output_pipeline.py` kết xuất từng video đầu ra), tách biệt hoàn toàn và hiện đại hơn so với các pipeline reup cũ.
3.  **Khuyến nghị:** **HOÀN TOÀN ĐÁNG NÂNG CẤP**, không nên thay thế. Hệ thống lõi đã được xây dựng rất tốt và tương thích với hầu hết các công nghệ mới. Việc nâng cấp chỉ cần tập trung giải quyết các khoảng cách đồng bộ hóa nhỏ ở giao diện (như hỗ trợ thêm ảnh tĩnh và cải tiến giao diện timeline).
