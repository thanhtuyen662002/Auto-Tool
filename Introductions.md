# PROMPT 0 — MASTER PROMPT CHO AGENT CODE

Bạn là Senior Fullstack Engineer kiêm Video Processing Engineer.
Hãy giúp tôi xây dựng dự án tên **Auto Tool**.

## Mục tiêu dự án

Auto Tool là một ứng dụng local dùng để tự động dựng lại video sản phẩm từ một folder video đầu vào.

Người dùng sẽ cung cấp:

* Folder chứa nhiều video sản phẩm
* Thông tin sản phẩm
* Số lượng video đầu ra mong muốn
* Độ dài video đầu ra
* Mức độ chỉnh sửa các thuộc tính như:

  * Cường độ cắt ghép
  * Biến đổi tốc độ
  * Nhiễu hạt nhẹ
  * Zoom/crop motion
  * Overlay bên dưới
  * Subtitle
  * Voiceover
  * CTA

Tool sẽ tự động:

1. Đọc toàn bộ video trong folder input
2. Phân tích metadata video bằng FFmpeg/ffprobe
3. Cắt video thành nhiều đoạn nhỏ
4. Trộn các đoạn thành timeline mới
5. Tạo nội dung voiceover/subtitle/CTA bằng Gemini thông qua adapter
6. Tạo voiceover bằng TTS thông qua adapter
7. Tạo subtitle `.srt` hoặc `.ass`
8. Thêm overlay bên dưới video để subtitle chạy phía trên
9. Thêm chỉnh sửa nhẹ:

   * Speed variation
   * Grain nhẹ
   * Crop về 9:16
   * Zoom motion nhẹ
10. Render ra nhiều video trong output folder
11. Xuất kèm file JSON log/script/subtitle cho từng video

## Giới hạn quan trọng

Không xây hệ thống quá lớn.

Version đầu tiên KHÔNG làm:

* Không tự động tải video từ TikTok
* Không login TikTok
* Không auto post
* Không bypass watermark
* Không né bản quyền
* Không microservice
* Không Kafka
* Không Docker bắt buộc
* Không workflow kéo thả phức tạp
* Không dashboard lớn
* Không nhiều agent tự quyết định

Chỉ làm app local nhỏ, dễ chạy, dễ debug.

Tool chỉ dùng cho video người dùng sở hữu, được phép dùng lại, hoặc có quyền remix/repost.

## Tech stack yêu cầu

Backend:

* Python 3.11+
* FastAPI cho API local
* FFmpeg/ffprobe cho xử lý video
* SQLite để lưu project/job/render log
* Pydantic để validate config
* Google GenAI SDK thông qua adapter riêng
* TTS thông qua adapter riêng, có thể mock trước

Frontend:

* React
* TypeScript
* Vite
* TailwindCSS
* UI đơn giản, không phức tạp

Cấu trúc repo mong muốn:

```txt
auto-tool/
  backend/
    app/
      main.py
      config.py
      database.py

      modules/
        project/
        media_scanner/
        segmenter/
        timeline_builder/
        script_writer/
        voice_generator/
        subtitle_generator/
        renderer/
        qa_checker/

      adapters/
        ffmpeg_adapter.py
        gemini_adapter.py
        tts_adapter.py

      schemas/
        project_schema.py
        render_schema.py
        media_schema.py

      workers/
        render_worker.py

      utils/
        file_utils.py
        path_utils.py
        logger.py

    requirements.txt
    README.md

  frontend/
    src/
      main.tsx
      App.tsx
      pages/
        CreateProjectPage.tsx
        RenderSettingsPage.tsx
        RenderQueuePage.tsx
        ResultPage.tsx

      components/
        FolderInput.tsx
        ProductInfoForm.tsx
        EffectSliders.tsx
        PresetSelector.tsx
        RenderProgress.tsx
        ResultList.tsx

    package.json
    README.md

  examples/
    product_config.example.json

  README.md
```

## Nguyên tắc code

* Code rõ ràng, chia module nhỏ
* Ưu tiên chạy được hơn là hoàn hảo
* Mỗi module có trách nhiệm riêng
* Có log rõ ràng
* Có xử lý lỗi
* Không hardcode path
* Không hardcode Gemini model
* Không hardcode TTS provider
* Tất cả config quan trọng nằm trong JSON hoặc `.env`
* Khi render lỗi phải lưu log để debug
* Không xóa file gốc của người dùng
* Output phải nằm trong folder riêng theo project

## Output mong muốn

Sau khi build xong MVP, tôi có thể chạy:

```bash
cd backend
python -m app.main --config ../examples/product_config.example.json
```

Và nhận được:

```txt
outputs/
  kaw-xmax10-2026-05-30/
    video_001.mp4
    video_001_script.json
    video_001_sub.srt
    video_001_log.json

    video_002.mp4
    video_002_script.json
    video_002_sub.srt
    video_002_log.json

    project_summary.json
```

Hãy bắt đầu bằng việc tạo architecture, file structure và code nền tảng tối thiểu. Không làm quá rộng.
