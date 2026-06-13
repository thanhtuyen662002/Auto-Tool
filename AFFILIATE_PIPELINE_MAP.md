# Bản đồ Dòng chảy Kết xuất Video Affiliate (Affiliate Pipeline Map)

Tài liệu này mô tả chi tiết dòng chảy dữ liệu (Data Flow) và quy trình kết xuất của luồng công việc **Product Video Builder** từ thiết lập dự án ban đầu cho đến khi tạo ra video thành phẩm hoàn chỉnh.

---

## 1. Sơ đồ Pipeline Kết xuất (Mermaid Diagram)

```mermaid
graph TD
    %% Giai đoạn 1: Khởi tạo cấu hình dự án
    subgraph Giai đoạn 1: Thiết lập & Quét dữ liệu
        Config[ProjectConfig: Tên, Folder, Product Info, Preset, AI Settings]
        Scanner[Media Scanner: Quét và thu thập metadata video nguồn]
        Segmenter[Segmenter: Cắt video nguồn thành các segment thô]
        Config --> Scanner
        Scanner --> Segmenter
    end

    %% Giai đoạn 2: Lọc & Chấm điểm phân cảnh
    subgraph Giai đoạn 2: Đánh giá & Lọc phân cảnh
        Scorer[Segment Scorer: Tính điểm Brightness, Sharpness, Motion, Stability, Freeze]
        Report[Scoring Report: Xuất file segment_scoring_report.json]
        Filter[Media Filter Service: Đối chiếu SQLite, loại bỏ excluded, ưu tiên favorite]
        Segmenter --> Scorer
        Scorer --> Report
        Scorer --> Filter
    end

    %% Giai đoạn 3: Dựng dòng thời gian
    subgraph Giai đoạn 3: Dựng dòng thời gian (Timeline)
        TimelineBuilder[Product Timeline Builder: Ánh xạ segment vào slots của Template]
        TimelineReport[Timeline Report: Xuất file video_xxx_timeline.json]
        CropSafety[Crop Safety Service: Tính điểm crop khung hình 9:16 và quyết định blur background]
        Filter --> TimelineBuilder
        TimelineBuilder --> TimelineReport
        TimelineBuilder --> CropSafety
    end

    %% Giai đoạn 4: Tạo tài nguyên thuyết minh & hiệu ứng
    subgraph Giai đoạn 4: Xử lý & Tạo Tài nguyên
        ScriptGen[Script Writer: AI Gemini / Manual sinh Hook, Body, CTA]
        VoiceGen[Voice Generator: Gọi TTS, căn chỉnh thời gian & chia nhỏ tiếng đọc]
        VoiceNormalizer[Audio Normalizer: Chuẩn hóa âm thanh và chèn khoảng lặng]
        SubGen[Subtitle Generator: Tạo file phụ đề SRT & ASS theo Preset Visual Style]
        MusicSelect[Music Selector: Chọn nhạc nền từ folder cấu hình]
        
        CropSafety --> ScriptGen
        ScriptGen --> VoiceGen
        VoiceGen --> VoiceNormalizer
        VoiceGen --> SubGen
        VoiceNormalizer --> SubGen
        CropSafety --> MusicSelect
    end

    %% Giai đoạn 5: Kết xuất & Kiểm định chất lượng
    subgraph Giai đoạn 5: Render & QA Đầu ra
        Renderer[Renderer: FFmpeg cắt, crop, thay đổi tốc độ và ghép các clip visual]
        OverlayRenderer[Overlay Renderer: Ghi đè khung overlay nhận diện & mix audio Sidechain compression]
        QA[QA Checker: Đọc metadata, kiểm tra thời lượng, độ phân giải & tính toàn vẹn]
        Summary[Summary Builder: Tạo project_summary.json và đóng gói Export Pack]

        Renderer --> OverlayRenderer
        VoiceNormalizer --> OverlayRenderer
        SubGen --> OverlayRenderer
        MusicSelect --> OverlayRenderer
        OverlayRenderer --> QA
        QA --> Summary
    end
```

---

## 2. Chi tiết từng bước thực thi trong Pipeline

Pipeline được điều phối chính bởi [render_worker.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/render_worker.py) và kết xuất độc lập từng video bởi [output_pipeline.py](file:///d:/Projects/Auto-Tool/backend/app/modules/render_worker/output_pipeline.py).

### Bước 1: Thu thập cấu hình & Quét video nguồn
- **Đầu vào:** `ProjectConfig` chứa thông tin sản phẩm và đường dẫn thư mục nguồn.
- **Thực thi:** 
  1. `MediaScanner` quét toàn bộ thư mục tìm các tệp video hợp lệ, ghi nhận codec, thời lượng, và độ phân giải.
  2. `Segmenter` thực hiện phân đoạn tự động các video nguồn thành các segment thô có thời lượng trung bình dựa trên tham số `cut_intensity`.

### Bước 2: Chấm điểm chất lượng phân cảnh (Segment Scoring)
- **Thực thi:** 
  1. `SegmentScorer` tiến hành trích xuất một số khung hình mẫu (`FrameSampler`) của từng segment.
  2. `SegmentAnalyzer` tính toán các chỉ số: độ sáng (contrast), độ sắc nét (Laplacian variance), biên độ chuyển động (motion vector) để cho điểm từ 0.0 đến 1.0. Các cảnh mờ, tối, hoặc bị đóng băng (freeze) sẽ bị đánh dấu loại trừ (`is_rejected`).
  3. Xuất báo cáo chấm điểm vào tệp `segment_scoring_report.json`.

### Bước 3: Lọc & Dựng Dòng thời gian (Timeline Building)
- **Thực thi:**
  1. `MediaFilterService` đọc lịch sử đánh giá của người dùng từ SQLite (loại bỏ video/cảnh bị exclude, đánh dấu yêu thích).
  2. `ProductTimelineBuilder` tải Timeline Template được chỉ định (như `ugc_reviewer_natural`), sau đó phân bổ các segment vào từng slot tỉ lệ (Hook, Product, Demo, Benefit, CTA) dựa trên điểm chất lượng và độ khớp tag.
  3. `CropSafetyService` phân tích bố cục hình ảnh xem cảnh quay khi crop dọc 9:16 có bị mất chi tiết quan trọng không, nếu có sẽ tự động kích hoạt chế độ làm mờ nền (blur background).

### Bước 4: Tạo tài nguyên lồng tiếng, phụ đề & nhạc nền
- **Thực thi:**
  1. `ScriptWriter` / `ScriptVariantGenerator` gọi API Gemini để sinh kịch bản chi tiết (gồm thuyết minh, phụ đề hiển thị, caption mạng xã hội và hashtags).
  2. `VoiceGenerator` gửi các câu thoại thuyết minh đến `TTSManager` để sinh giọng đọc thuyết minh, tính toán thời lượng phát âm thực tế của từng câu thoại.
  3. `SubtitleGenerator` dựng dòng thời gian phụ đề và sinh các file phụ đề `.srt` (phụ đề thường) và `.ass` (phụ đề styled trang trí).
  4. `MusicSelector` lựa chọn một bài nhạc nền phù hợp trong thư mục nhạc cấu hình.

### Bước 5: Thực hiện Render Visual & Mix Audio (FFmpeg)
- **Thực thi:**
  1. `Renderer` gọi FFmpeg để thực hiện cắt, crop khung hình, thay đổi tốc độ (speed up/down) cho từng clip visual trên timeline và nối chúng lại thành tệp video visual tạm thời.
  2. `OverlayRenderer` tạo hình ảnh overlay (gồm logo thương hiệu, khung CTA) bằng thư viện PIL.
  3. FFmpeg chạy lệnh cuối cùng để: Burn-in phụ đề ASS, phủ ảnh Overlay lên video, mix giọng đọc lồng tiếng và nhạc nền (có tính năng sidechain compression để tự động dìm nhạc nền khi có tiếng nói).

### Bước 6: Kiểm định QA và Đóng gói (Quality Assurance)
- **Thực thi:**
  1. `QA_Checker` (qua `check_output_video`) kiểm tra độ dài video thực tế có khớp thiết lập, định dạng audio có đúng chuẩn, file phụ đề có đồng bộ hay không.
  2. Tạo báo cáo log chi tiết cho từng video vào file `video_xxx_log.json` và tổng kết toàn bộ dự án vào file `project_summary.json`.
