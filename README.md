# Auto Tool

## Auto Tool v0.2 Overview

Auto Tool v0.2.0-rc1 is a local release candidate focused on a practical product-video workflow:

```txt
Import product info
-> Select industry preset
-> Scan source videos
-> Review source media
-> Render preview
-> Edit script
-> Render full batch
-> Review quality
-> Rerender bad outputs
-> Manage captions
-> Export content
```

The v0.2 pass does not add auto-download, auto-posting, account login, cloud render, multi-user, licensing, watermark removal, or heavy AI vision. It focuses on QA, integration cleanup, release docs, and a repeatable real-product test pack.

## Quick Start

Backend:

```bash
cd backend
pip install -r requirements-dev.txt
py -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Build checks:

```bash
cd backend
pytest
```

```bash
cd frontend
npm run build
```

## Real Product Test Pack

The v0.2 test pack is in `examples/real_product_test_pack/`. It contains configs, product input text, expected-output notes, and empty media folders under `examples/sample_videos/real_product_test_pack/`.

Place real product videos in one of these folders:

```txt
examples/sample_videos/real_product_test_pack/projector_kaw_xmax10/
examples/sample_videos/real_product_test_pack/handheld_fan_jisulife/
examples/sample_videos/real_product_test_pack/sunscreen_jacket_guno/
examples/sample_videos/real_product_test_pack/home_gadget_generic/
```

## v0.2 Smoke Test

From `backend/`:

```bash
python -m app.tools.v02_smoke_test --config ../examples/real_product_test_pack/configs/projector_kaw_xmax10.json --preview-only --skip-tts-online
```

Full batch:

```bash
python -m app.tools.v02_smoke_test --config ../examples/real_product_test_pack/configs/projector_kaw_xmax10.json --full
```

If no real source videos are present, the smoke test creates synthetic test videos and returns `success_with_warnings`. When real videos exist, it uses them.

## Import Inbox / Product Drafts

Auto Tool can save product imports as local Product Drafts in SQLite. This is used by the Shopee Chrome Extension flow:

```txt
Shopee product page
-> Chrome Extension Extract Product Info
-> Send to Auto Tool
-> Backend normalizes and validates product info
-> Draft is saved in Import Inbox
-> User reviews or edits draft
-> Apply to existing project or create a new project from draft
```

Frontend page:

```txt
/import-inbox
```

API:

```txt
GET    /api/product-drafts
GET    /api/product-drafts/{draft_id}
PUT    /api/product-drafts/{draft_id}
POST   /api/product-drafts/{draft_id}/archive
DELETE /api/product-drafts/{draft_id}
POST   /api/product-drafts/clear-archived
POST   /api/product-drafts/{draft_id}/apply-to-project/{project_id}
POST   /api/product-drafts/{draft_id}/create-project
GET    /api/projects
```

Product drafts are stored locally on the user's machine. A draft can contain product description, price, Shopee link, shop info, raw text, normalized product fields, validation warnings, and source metadata. Users can archive or delete drafts at any time. Auto Tool does not cloud-sync drafts and does not send draft data to third-party servers.

Shopee Extension imports also store `extractor_debug`, including field-level extraction method, confidence, missing fields, and warnings. Import responses that save a draft include `import_inbox_url` so the extension can open the Import Inbox or a specific draft directly.

## Douyin Reup

Douyin Reup la workflow local cho cac video Douyin da duoc nguoi dung tai san vao may. Tool khong tai video tu Douyin, khong bypass watermark va khong xoa watermark. OCR hard-sub chi chay local tren video nguoi dung da co san. Nguoi dung can tu dam bao co quyen su dung video, subtitle va nhac nen.

Luồng xử lý:

```txt
Chọn thư mục video Douyin local
-> Scan video và phát hiện subtitle
-> Ưu tiên file .srt đi kèm
-> Nếu không có .srt thì thử subtitle nhúng
-> Nếu vẫn không có subtitle thì dùng ASR optional
-> Neu ASR fail hoac khong co subtitle thi fallback OCR hard-sub tieng Trung
-> Dịch subtitle Trung -> Việt bằng Gemini
-> Guard timing và wrap subtitle
-> Tạo Subtitle Review Document để sửa subtitle thủ công
-> Approve subtitle đã sửa
-> Render video dọc với overlay/subtitle/nhạc nền từ bản đã approve
-> Ghi log riêng từng video và summary
```

Frontend page:

```txt
/douyin-reup
/subtitle-review
```

API:

```txt
POST /api/douyin-reup/scan
GET  /api/douyin-reup/presets
GET  /api/douyin-reup/presets/{preset_id}
POST /api/douyin-reup/apply-preset
POST /api/douyin-reup/recommend-preset
POST /api/douyin-reup/one-click
POST /api/douyin-reup/process
POST /api/douyin-reup/ocr-test
GET  /api/jobs/{job_id}
GET  /api/douyin-reup/jobs/{job_id}/results
POST /api/douyin-reup/jobs/{job_id}/retry-with-preset
GET  /api/subtitle-review/documents
GET  /api/subtitle-review/documents/{document_id}
PUT  /api/subtitle-review/documents/{document_id}/lines/{line_index}
PUT  /api/subtitle-review/documents/{document_id}
POST /api/subtitle-review/documents/{document_id}/approve
POST /api/subtitle-review/documents/{document_id}/render
POST /api/subtitle-review/render-approved
GET  /api/subtitle-review/documents/{document_id}/quality
POST /api/subtitle-review/documents/{document_id}/quality/refresh
GET  /api/subtitle-review/documents/{document_id}/quality/flagged-lines
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/suggest-rewrite
```

One-click presets:

```txt
safe_review           Default, translate then stop for subtitle review.
fast_auto             Auto-render known-good batches without manual subtitle review.
ocr_priority          Prefer hardcoded Chinese subtitle OCR before ASR.
voice_priority        Prefer ASR for clear speech videos.
clean_subtitle_only   Burn clean subtitles without overlay or BGM.
music_recut           Auto-render with stronger background music mix.
```

One-click request example:

```json
{
  "project_name": "douyin-one-click-safe-review",
  "source_folder": "D:\\Videos\\douyin",
  "output_folder": "D:\\Videos\\outputs",
  "preset_id": "safe_review",
  "bgm_folder": "D:\\Music\\bgm",
  "visual_style_preset_id": "clean_review_light",
  "process_mode": "all_videos",
  "max_videos": null,
  "selected_video_paths": [],
  "review_subtitles_before_render": true,
  "auto_render_after_translation": false,
  "advanced_overrides": {}
}
```

Config examples:

```txt
examples/douyin_reup_test_pack/configs/one_click_safe_review.json
examples/douyin_reup_test_pack/configs/one_click_fast_auto.json
examples/douyin_reup_test_pack/configs/one_click_ocr_priority.json
examples/douyin_reup_test_pack/configs/one_click_voice_priority.json
```

### Subtitle Quality Scoring

Moi Subtitle Review Document duoc cham diem rule-based ngay sau khi tao. UI hien thi average score, cac dong can review, critical/warning, bo loc, dieu huong den dong bi flag va approval guard. Cac rule bao gom do dai, so dong, reading speed, duration, ky tu Trung con sot, markdown/JSON leak, ky tu la, OCR/ASR confidence, source-target mismatch, lap text va timestamp overlap/out-of-range.

Preset `safe_review` bat `auto_mark_low_quality_lines=true`; dong co score thap hoac critical se duoc danh dau `needs_fix`. Bao cao duoc luu tai `subtitle_quality_report.json`, va `douyin_reup_summary.json` co them tong hop `subtitle_quality`. Nut `Suggest shorter translation` tao goi y cho tung dong, khong tu dong rewrite toan bo subtitle.

Known limitations:

- Quality score la rule-based, khong dam bao phat hien moi loi dich.
- Tool khong the ket luan ban dich dung 100%; user van nen kiem tra cac dong bi flag truoc khi render.
- OCR/ASR confidence thap chi la tin hieu can review, khong phai ket luan chac chan.
- Rewrite suggestion mac dinh la local rule-based khi khong cau hinh AI provider.

### Subtitle Auto Shortener and Safe Rewrite

Trong Subtitle Review, cac dong bi quality flag co nut `Suggest rewrite`. Tool tao toi da 3 goi y ngan hon, tinh truoc quality score/CPS, kiem tra keyword, thuong hieu, so lieu, don vi, markdown/JSON, ky tu Trung va forbidden claims. User chon `Apply` de cap nhat `edited_text`; quality report duoc refresh ngay sau do.

Bulk rewrite cho phep chon style, issue type va so dong toi da. `Auto apply only safe high-score suggestions` chi ap dung khi suggestion khong co safety warning, ngan hon ban goc va co quality score tu 85% tro len. Mac dinh tinh nang nay tat.

API:

```txt
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/rewrite-suggestions
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/apply-rewrite
POST /api/subtitle-review/documents/{document_id}/rewrite-flagged-lines
```

Rewrite data duoc luu trong SQLite, line `rewrite_history` va `subtitle_rewrite_log.json`. `douyin_reup_summary.json` co them `subtitle_rewrite` voi so suggestion da tao/ap dung va quality improvement trung binh.

Known limitations:

- Rewrite suggestion khong dam bao dung 100%; user van nen kiem tra truoc khi approve.
- AI co the dua ra goi y chua hoan hao du safety validator da chan cac loi ro rang.
- Auto apply chi nen dung cho suggestion an toan, ngan hon va score cao.
- Neu OCR/ASR source sai, rewrite tieng Viet van co the sai theo source ban dau.

### Final Output QA and Platform Export Pack

Sau moi video render thanh cong, Douyin Reup tu dong chay QA ky thuat bang ffprobe/FFmpeg. Report kiem tra file, duration, 9:16, resolution, FPS, H.264/AAC, file size, audio volume, subtitle/overlay artifact va subtitle safe zone. Ket qua duoc luu trong `video_XXX_final_qa.json`, `video_XXX_log.json`, `final_qa_summary.json` va `douyin_reup_summary.json`.

Results co tab `Final QA` de xem score/issue tung video, chay lai QA theo profile TikTok, Instagram Reels, YouTube Shorts hoac Generic Vertical, va retry render khi QA failed.

Platform Export Pack tao:

```txt
export_pack/{platform}/
  videos/
  subtitles/
  captions/captions.txt
  captions/captions.csv
  logs/
  qa/final_qa_summary.json
  posting_checklist.md
  export_manifest.json
```

API:

```txt
POST /api/final-output-qa/check
POST /api/final-output-qa/jobs/{job_id}/check
POST /api/douyin-reup/jobs/{job_id}/export-pack
GET  /api/douyin-reup/jobs/{job_id}/export-pack
```

Known limitations:

- Final QA la kiem tra ky thuat rule-based, khong thay the viec xem lai video bang mat.
- Subtitle visibility checker chua OCR lai video final de xac nhan chu da burn 100%.
- Platform profiles la goi y ky thuat local, khong dam bao luon khop chinh sach moi nhat.
- Tool khong tu dang video hoac dang nhap nen tang.

Mặc định `review_subtitles_before_render=true` và `auto_render_after_translation=false`, nên Douyin Reup sẽ dừng ở trạng thái `needs_review` sau khi dịch subtitle. Người dùng mở `/subtitle-review`, sửa từng dòng tiếng Việt với preview video, lưu, approve, rồi queue render từ subtitle đã duyệt. Nếu muốn giữ luồng render cũ, đặt `review_subtitles_before_render=false` hoặc `auto_render_after_translation=true`.

Ví dụ request scan:

```json
{
  "source_folder": "D:\\Videos\\douyin"
}
```

Ví dụ request process:

```json
{
  "project_name": "douyin-reup-test",
  "source_folder": "D:\\Videos\\douyin",
  "output_folder": "D:\\Videos\\outputs",
  "settings": {
    "enabled": true,
    "source_language": "zh",
    "target_language": "vi",
    "translation_provider": "gemini",
    "subtitle_source_priority": ["sidecar_srt", "embedded_subtitle", "asr", "ocr_hardsub"],
    "use_sidecar_srt": true,
    "use_embedded_subtitle": true,
    "use_asr_if_no_subtitle": true,
    "asr_provider": "faster_whisper",
    "asr_model_size": "medium",
    "asr_device": "auto",
    "use_ocr_if_asr_failed": true,
    "use_ocr_if_no_subtitle": true,
    "ocr_provider": "easyocr",
    "ocr_language": "ch",
    "ocr_sample_fps": 2.0,
    "ocr_region_mode": "bottom_auto",
    "ocr_min_confidence": 0.55,
    "prefer_ocr_over_asr_when_text_visible": false,
    "visual_style_preset_id": "clean_review_light",
    "burn_subtitle": true,
    "add_overlay": true,
    "music_folder": "D:\\Music\\bgm",
    "bgm_volume": 0.16,
    "original_audio_volume": 0.85,
    "duck_bgm_when_voice": false,
    "resolution": "1080x1920",
    "fps": 30,
    "process_mode": "all",
    "max_videos": null,
    "selected_video_paths": [],
    "keep_temp": false,
    "review_subtitles_before_render": true,
    "auto_render_after_translation": false
  }
}
```

Output mẫu:

```txt
outputs/douyin-reup-test-douyin-reup-2026-06-09-120000/
  video_001/
    source.mp4
    video_001_source_zh.srt
    video_001_vi.srt
    video_001_vi_fixed.srt
    douyin_001_vi.ass
    douyin_001_overlay.png
    douyin_001.mp4
    video_001_log.json
  douyin_reup_summary.json
```

Ghi chú:

- Gemini API key lấy từ trang `Cài đặt chung` hoặc `.env`.
- Nếu Gemini lỗi, subtitle nguồn được giữ lại và job ghi warning, không crash toàn batch.
- ASR dùng `faster-whisper`. Khi chạy backend bằng source code, cài bằng `py -m pip install -r backend/requirements.txt`. Khi chạy exe, package ASR được bundle trong exe nhưng model Whisper vẫn cần tải từ HuggingFace ở lần nhận diện đầu tiên.
- Nếu runtime thiếu asset VAD `silero_vad_v6.onnx`, ASR sẽ tự retry không dùng VAD thay vì làm fail output. Bản exe build mới cũng bundle thư mục `faster_whisper/assets`.
- OCR hard-sub duoc dung sau sidecar/embedded/ASR, hoac khi bat `prefer_ocr_over_asr_when_text_visible`. Provider mac dinh la `easyocr`; co the doi sang `paddleocr` hoac `mock_ocr` de test pipeline khong can model OCR.
- Khi mo app, Auto Tool tu kiem tra va tai runtime can thiet trong background: FFmpeg, Piper voice/model va OCR provider. OCR package duoc cai vao `%LOCALAPPDATA%\AutoTool\python_packages\pyXX` neu chua co trong environment.
- PaddleOCR can `paddlepaddle` wheel phu hop voi Python dang chay. Neu paddlepaddle khong ho tro Python hien tai, dung EasyOCR mac dinh.
- Co the tat auto-install bang `AUTO_TOOL_AUTO_INSTALL=0`, hoac chi tat OCR auto-install bang `AUTO_TOOL_AUTO_INSTALL_OCR=0`.
- Xem trang thai runtime qua `GET /api/system/dependencies`; UI Douyin Reup cung hien thi trang thai OCR runtime.
- Dùng file `.srt` đi kèm video là cách ổn định và nhanh nhất; ASR/OCR chỉ nên dùng khi video không có subtitle nguồn.
- Nếu nhạc nền lỗi, renderer sẽ thử xuất video chỉ với audio gốc.

## Douyin Reup Real Batch QA

Real batch QA pack:

```txt
examples/douyin_reup_test_pack/
```

Đặt video Douyin thật vào:

```txt
sample_videos/douyin_reup_test_pack/
```

Chạy review mode:

```bash
cd backend
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_review_mode.json
```

Chạy test tích hợp không cần Gemini:

```bash
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_review_mode.json --mock-translation
```

Chạy auto render mode:

```bash
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_auto_render.json --auto-render
```

Flags:

```txt
--scan-only
--translate-only
--review-mode
--render-approved
--auto-render
--skip-asr
--mock-translation
--debug
```

Review mode dừng sau bước dịch và tạo Subtitle Review Document. User mở `/subtitle-review`, sửa subtitle, approve, rồi render approved. Auto render mode bỏ qua review và render ngay sau khi dịch/timing guard.

Retry failed videos:

```txt
POST /api/douyin-reup/jobs/{job_id}/retry-failed
POST /api/douyin-reup/jobs/{job_id}/retry-with-preset
```

```json
{
  "retry_steps": ["asr", "translation", "render"],
  "settings": {}
}
```

Retry chỉ chọn output `status=failed` từ job cũ. Nếu output failed đã có `source_srt_file` hoặc `translated_srt_file`, retry sẽ ưu tiên dùng lại file đó thay vì chạy lại ASR/dịch không cần thiết.

Retry with preset example:

```json
{
  "preset_id": "ocr_priority",
  "video_ids": ["video_001"],
  "retry_steps": ["asr", "translation", "render"],
  "settings": {
    "ocr_sample_fps": 3.0
  }
}
```

`retry-with-preset` keeps retry cache from the failed job and records preset changes in each output `retry_history`.

Common errors and fixes:

```txt
Không tìm thấy faster-whisper:
  Cài `py -m pip install -r backend/requirements.txt` hoặc chạy với `--skip-asr`.

Folder rỗng hoặc sai path:
  Kiểm tra `source_folder` trong config và folder `sample_videos/douyin_reup_test_pack/`.

Gemini translation failed:
  Bổ sung API key hoặc dùng `--mock-translation` để test tích hợp local.

BGM folder rỗng:
  Output vẫn render, summary sẽ có warning.

FFmpeg render lỗi:
  Xem `failed_step=render`, `video_001_log.json`, và `douyin_reup_summary.json`.
```

Performance baseline template:

```txt
docs/DOUYIN_REUP_PERFORMANCE_BASELINE.md
```

Known limitations:

```txt
- Nếu video chỉ có chữ Trung dính trên màn hình và không có lời thoại rõ, ASR có thể không tạo được SRT tốt.
- OCR hard-sub da co pipeline local, nhung ket qua can review thu cong vi OCR co the nhan sai chu.
- Bản dịch tự động cần user kiểm tra lại.
- Người dùng cần đảm bảo quyền sử dụng video và nhạc nền.
```

## v0.2 QA Checklist

Use:

```txt
docs/V0_2_QA_CHECKLIST.md
docs/V0_2_BUG_BASH.md
docs/V0_2_PERFORMANCE_BASELINE.md
docs/SHOPEE_EXTENSION_QA_CHECKLIST.md
```

The smoke test prints a JSON result with step status, output folder, warnings/errors, and a `performance_baseline` block.

## Known Limitations

- Auto Tool does not download videos from TikTok or other platforms.
- Auto Tool does not post videos automatically.
- Auto Tool does not log in to user accounts.
- Auto Tool does not verify product information on the internet.
- Segment scoring and crop safety are heuristic and are not guaranteed to be 100% accurate.
- Quality score is a technical estimate; users still need to watch outputs manually.
- Edge-TTS needs network access and can fail.
- Piper needs a local model.
- Use only media and music you have the right to edit or remix.

Auto Tool là công cụ local hỗ trợ tạo video recut ngắn cho sản phẩm từ một thư mục video nguồn. Mục tiêu hiện tại là cung cấp một pipeline chạy được trên máy cá nhân: scan video, cắt segment, dựng timeline, tạo script bằng Gemini, tạo voice tiếng Việt, burn subtitle/overlay, thêm nhạc nền và xuất nhiều video đầu ra.

Dự án đang ở giai đoạn MVP có CLI, FastAPI local, React UI và bản Windows exe. Tool chưa phải hệ thống production hoàn chỉnh, nhưng đã đủ để developer tiếp tục phát triển các phần segment thông minh, timeline theo sản phẩm và workflow UI tốt hơn.

## Tính Năng Hiện Tại

- CLI render batch từ file JSON config.
- FastAPI local để frontend tạo project, scan video, render preview/full batch và lấy kết quả.
- React + TypeScript UI cho luồng tạo project, chỉnh preset, preview, sửa script và render full batch.
- Scan folder video đầu vào, chỉ nhận `.mp4`, `.mov`, `.mkv`, `.webm`.
- Lấy metadata video bằng `ffprobe`.
- Cắt video thành segment logic theo `cut_intensity`.
- Smart Segment Scoring bằng OpenCV/NumPy để ưu tiên đoạn sáng, rõ, có chuyển động vừa phải.
- Product-aware Timeline Templates để dựng cấu trúc `Hook -> Product -> Demo -> Benefit -> CTA`.
- Product Assets từ Import Inbox để chọn `main_product`, `reference`, `poster`, `thumbnail`.
- Product Reference Prompt Pack tạo accuracy lock, storyboard 5 cảnh, full prompt, negative prompt và JSON prompt để copy sang công cụ AI video/image bên ngoài.
- Build timeline weighted random theo điểm chất lượng segment, tag và template slot cho nhiều output.
- Render visual recut bằng FFmpeg theo tỷ lệ dọc `1080x1920`.
- Crop Safety Guard phân tích frame mẫu để giảm rủi ro crop mất sản phẩm, tự fallback sang nền mờ khi video ngang có nội dung sát mép.
- Generate script/subtitle bằng Gemini, có hỗ trợ nhiều API key và tự xoay key khi key lỗi.
- Script Variant Generator tạo script khác nhau cho từng video trong batch, ưu tiên style phù hợp với timeline template.
- Cho phép nhập Gemini API keys trên giao diện.
- Cho phép render preview một video ngắn trước khi render full batch.
- Cho phép sửa script sau preview rồi lưu custom script cho full batch.
- TTS tiếng Việt qua provider system: Edge TTS -> Piper -> gTTS -> silent fallback.
- Burn overlay đáy video, subtitle `.ass`, voiceover và nhạc nền.
- QA checker sau render, phân loại `success`, `warning`, `failed`.
- Mỗi output có log riêng `video_XXX_log.json` hoặc `preview_001_log.json`.
- Project summary có thống kê số output thành công, thất bại, warning và danh sách lỗi.
- Windows exe launcher có thể tự kiểm tra/cài FFmpeg, Piper và voice tiếng Việt một lần vào `%LOCALAPPDATA%\AutoTool`.

## Giới Hạn Sử Dụng Hợp Pháp

Chỉ sử dụng Auto Tool với video, hình ảnh, âm thanh và nội dung mà bạn có quyền sử dụng. Không dùng tool để bypass watermark, reupload nội dung vi phạm bản quyền, giả mạo review, đưa claim sai sự thật hoặc né chính sách nền tảng.

Khi tạo nội dung quảng cáo sản phẩm:

- Không bịa thông số kỹ thuật.
- Không dùng claim tuyệt đối như "tốt nhất", "số 1", "100% hiệu quả" nếu không có bằng chứng.
- Không dùng nhạc hoặc video không có quyền thương mại.
- Tuân thủ điều khoản của TikTok, Shopee, Reels, Gemini API và các dịch vụ TTS.
- Kiểm tra video đầu ra trước khi đăng công khai.

## Tech Stack

Backend:

- Python 3.10+
- Pydantic v2
- FastAPI
- Uvicorn
- SQLite
- FFmpeg / FFprobe
- edge-tts
- Piper TTS optional
- gTTS backup
- PyInstaller cho bản Windows exe

Frontend:

- React 19
- TypeScript
- Vite
- TailwindCSS
- react-router-dom

## Cấu Trúc Project

```txt
Auto-Tool/
  backend/
    app/
      adapters/
      modules/
      schemas/
      utils/
      api.py
      config.py
      database.py
      launcher.py
      main.py
    data/
    dist/
    requirements.txt
    requirements-build.txt
    README.md

  frontend/
    src/
      api/
      components/
      pages/
      types/
      utils/
    package.json
    README.md

  examples/
    product_config.example.json
    sample_videos/
    music/
    outputs/

  packaging/
    build_windows_exe.ps1

  docs/
    DEVELOPMENT_PLAN.md
    TROUBLESHOOTING.md
```

## Cài Đặt Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Nếu cần build exe:

```powershell
py -m pip install -r requirements-build.txt
```

## Cài Đặt Frontend

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Frontend mặc định gọi API ở:

```txt
http://localhost:8000
```

Biến môi trường frontend:

```txt
VITE_API_BASE_URL=http://localhost:8000
```

## Cài FFmpeg

Auto Tool cần `ffmpeg` và `ffprobe`.

Cài bằng winget:

```powershell
winget install Gyan.FFmpeg
ffmpeg -version
ffprobe -version
```

Nếu chạy bằng exe, launcher sẽ cố tự tải FFmpeg Windows vào:

```txt
%LOCALAPPDATA%\AutoTool\tools\ffmpeg
```

Launcher cũng tự tải Piper Windows và voice tiếng Việt mặc định vào:

```txt
%LOCALAPPDATA%\AutoTool\tools\piper
%LOCALAPPDATA%\AutoTool\tools\piper\models
```

Sau khi tải xong, app tự set `PATH`, `PIPER_MODEL_PATH` và `PIPER_CONFIG_PATH` cho process đang chạy. Người dùng mở file exe lần đầu có thể phải chờ lâu hơn vì app đang tải FFmpeg/Piper/model; các lần sau sẽ dùng lại file đã cài.

Nếu muốn chỉ định FFmpeg thủ công:

```powershell
$env:AUTO_TOOL_FFMPEG_DIR="D:\Tools\ffmpeg\bin"
```

Nếu muốn tắt auto install:

```powershell
$env:AUTO_TOOL_AUTO_INSTALL="0"
```

## Cấu Hình `.env`

Backend tự đọc `.env` trong `backend`, project root hoặc cùng thư mục với file exe.

Ví dụ:

```txt
GEMINI_API_KEY=your_single_key_here
GEMINI_API_KEYS=key_1,key_2,key_3
AUTO_TOOL_ALLOW_SCRIPT_FALLBACK=0
AUTO_TOOL_TTS_VOICE=vi-VN-HoaiMyNeural
AUTO_TOOL_TTS_PROVIDER=edge_tts
AUTO_TOOL_TTS_FALLBACK_PROVIDER=piper
AUTO_TOOL_TTS_FORMAT=mp3
AUTO_TOOL_TTS_RETRIES=2
GOOGLE_TTS_CREDENTIALS_JSON_PATH=D:\Keys\google-tts-service-account.json
GOOGLE_TTS_ACCESS_TOKEN=optional_short_lived_oauth_token
GOOGLE_TTS_API_KEY=optional_legacy_api_key
PIPER_MODEL_PATH=D:\Models\piper\vi_VN-vais1000-medium.onnx
PIPER_CONFIG_PATH=D:\Models\piper\vi_VN-vais1000-medium.onnx.json
AUTO_TOOL_FFMPEG_DIR=D:\Tools\ffmpeg\bin
AUTO_TOOL_DB_PATH=D:\Projects\Auto-Tool\backend\data\autotool.db
AUTO_TOOL_PORT=8000
AUTO_TOOL_OPEN_BROWSER=1
```

Ghi chú:

- `GEMINI_API_KEY`: một Gemini key.
- `GEMINI_API_KEYS`: nhiều key, ngăn cách bằng dấu phẩy. UI cũng cho nhập nhiều key, mỗi dòng một key.
- `AUTO_TOOL_ALLOW_SCRIPT_FALLBACK=1`: cho phép dùng fallback script local khi Gemini lỗi. Chỉ nên bật khi debug/offline.
- `AUTO_TOOL_TTS_PROVIDER=edge_tts`: dùng Edge TTS online.
- `AUTO_TOOL_TTS_PROVIDER=google_cloud_tts`: dùng Google Cloud Text-to-Speech.
- `GOOGLE_TTS_CREDENTIALS_JSON_PATH`: service account JSON path cho Google Cloud TTS. Đây là cách ổn định nhất cho Cloud Text-to-Speech REST.
- `GOOGLE_TTS_ACCESS_TOKEN`: OAuth access token ngắn hạn cho Google Cloud TTS nếu muốn test nhanh.
- `GOOGLE_TTS_API_KEY`: fallback legacy. Cloud Text-to-Speech REST thường cần OAuth/service account, nên API key có thể bị Google từ chối.
- `AUTO_TOOL_TTS_FALLBACK_PROVIDER=piper`: provider fallback offline nếu Edge TTS lỗi.
- `AUTO_TOOL_TTS_PROVIDER=silent`: ép dùng silent audio để test nhanh pipeline.
- `AUTO_TOOL_TTS_VOICE=vi-VN-HoaiMyNeural`: voice nữ tiếng Việt mặc định.
- `AUTO_TOOL_TTS_RETRIES=2`: số lần retry Edge TTS, tối đa 5.
- `PIPER_MODEL_PATH` và `PIPER_CONFIG_PATH`: file model/config cho Piper offline.

Piper mặc định dùng model tiếng Việt rõ hơn:

```txt
Language: vi_VN
Quality: medium
Samplerate: 22,050Hz
Model: vi_VN-vais1000-medium
```
- `AUTO_TOOL_PORT`: cổng launcher/API.

## Chạy CLI

```powershell
cd backend
py -m app.main --config ../examples/product_config.example.json
```

CLI sẽ:

1. Load config JSON.
2. Scan video nguồn.
3. Tạo segment/timeline.
4. Render từng output.
5. Chạy QA.
6. Ghi `project_summary.json`.

Chạy sample project end-to-end:

```powershell
cd backend
py -m app.main --config ../examples/sample_project/product_config.example.json
```

Sample project có sẵn video dummy trong `examples/sample_project/sample_videos/sample_product`. Khi test sản phẩm thật, thay bằng 3-5 video nguồn dài hơn 4 giây.

## Chạy API

```powershell
cd backend
py -m uvicorn app.main:app --reload --port 8000
```

Health check:

```txt
GET http://localhost:8000/api/health
```

Endpoint chính:

```txt
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/scan
POST /api/projects/{project_id}/analyze-segments
POST /api/projects/{project_id}/render
POST /api/projects/{project_id}/crop-safety/analyze
GET  /api/projects/{project_id}/latest-script
PUT  /api/projects/{project_id}/script
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/results
GET  /api/files/video?path=...
GET  /api/presets
GET  /api/tts/providers
GET  /api/timeline-templates
GET  /api/script-variants/styles
POST /api/projects/{project_id}/generate-script-variants
```

Preview render:

```json
{
  "preview_only": true
}
```

Preview chỉ render 1 video, duration tối đa 8 giây, output nằm trong:

```txt
{output_folder}/preview
```

## Chạy Frontend

Terminal 1:

```powershell
cd backend
py -m uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Mở:

```txt
http://127.0.0.1:5173
```

## Chạy Một Process Cho UI Và API

Build frontend:

```powershell
cd frontend
npm run build
```

Chạy launcher:

```powershell
cd backend
py -m app.launcher
```

Launcher sẽ start FastAPI, serve frontend build và tự mở browser.

## Build Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows_exe.ps1
```

File exe sinh ra:

```txt
backend/dist/AutoTool.exe
```

Build Chrome Extension:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_chrome_extension.ps1
```

File extension zip sinh ra:

```txt
chrome-extension/auto-tool-shopee-extractor.zip
```

Khi gửi sang máy khác, người dùng có thể mở exe. App sẽ tạo database local ở:

```txt
%LOCALAPPDATA%\AutoTool\data\autotool.db
```

## Config JSON Mẫu

File mẫu:

```txt
examples/product_config.example.json
```

Ví dụ rút gọn:

```json
{
  "project_name": "kaw-xmax10",
  "source_folder": "./sample_videos/kaw_xmax10",
  "output_folder": "./outputs",
  "product": {
    "name": "Máy Chiếu 4K Android KAW XMAX10",
    "brand": "KAW",
    "description": "Máy chiếu giải trí gia đình nhỏ gọn, hỗ trợ 4K, Android 9.0.",
    "features": [
      "Hỗ trợ 4K",
      "Android 9.0",
      "Thiết kế nhỏ gọn"
    ],
    "cta": "Xem chi tiết sản phẩm ngay"
  },
  "render": {
    "output_count": 3,
    "duration": 12,
    "aspect_ratio": "9:16",
    "resolution": "1080x1920",
    "fps": 30
  },
  "effects": {
    "cut_intensity": 70,
    "speed_variation": 30,
    "grain": 15,
    "zoom_motion": 25,
    "overlay_height": 33,
    "subtitle_size": 84
  },
  "ai": {
    "text_model": "gemini-3.1-flash-lite",
    "tone": "friendly_reviewer",
    "language": "vi",
    "gemini_api_keys": []
  },
  "music": {
    "enabled": true,
    "source_folder": "./music",
    "source_file": null,
    "volume": 0.12,
    "fade_in": 0.5,
    "fade_out": 0.8,
    "duck_under_voice": false
  },
  "crop_safety": {
    "enabled": true,
    "mode": "auto_safe",
    "allow_blur_background": true,
    "reduce_zoom_on_risk": true,
    "reduce_overlay_on_risk": true
  }
}
```

Path tương đối trong CLI được resolve theo vị trí file config. Khi tạo project qua API/UI, backend cố resolve path theo current working directory, project root, `examples`, backend folder và thư mục exe.

## Output Folder Mẫu

Full batch:

```txt
examples/outputs/kaw-xmax10-2026-05-31-093000/
  video_001.mp4
  video_001_visual.mp4
  video_001_script.json
  video_001_sub.srt
  video_001_sub.ass
  video_001_voice.mp3
  video_001_voice_normalized.wav
  video_001_voice_text.txt
  video_001_timeline.json
  video_001_log.json
  video_002.mp4
  crop_safety_report.json
  segment_scoring_report.json
  script_variants.json
  project_summary.json
```

Preview:

```txt
examples/outputs/preview/
  preview_001.mp4
  preview_001_visual.mp4
  preview_001_script.json
  preview_001_sub.srt
  preview_001_sub.ass
  preview_001_voice.mp3
  preview_001_voice_normalized.wav
  preview_001_voice_text.txt
  preview_001_log.json
  crop_safety_report.json
  segment_scoring_report.json
  script_variants.json
  project_summary.json
```

`project_summary.json` có dạng:

```json
{
  "total_outputs": 3,
  "successful_outputs": 2,
  "failed_outputs": 1,
  "warnings_count": 4,
  "failed_items": [
    {
      "index": 3,
      "reason": "render_final failed: FFmpeg command failed"
    }
  ]
}
```

## How To Run E2E Test

Chạy toàn bộ test backend:

```powershell
cd backend
py -m pytest
```

Chạy riêng nhóm acceptance/E2E:

```powershell
cd backend
py -m pytest tests/e2e -q
```

E2E tests sẽ tạo video dummy bằng FFmpeg trong thư mục tạm, patch TTS để không gọi mạng, rồi chạy pipeline thật qua renderer/QA/API. Nếu FFmpeg không khả dụng, nhóm test media sẽ skip với message rõ.

## How To Test With Sample Videos

Sample project nằm ở:

```txt
examples/sample_project/
```

Nguồn video:

```txt
examples/sample_project/sample_videos/sample_product/
```

Chạy:

```powershell
cd backend
py -m app.main --config ../examples/sample_project/product_config.example.json
```

Expected output structure:

```txt
examples/sample_project/outputs/sample-product-YYYY-MM-DD-HHMMSS/
  video_001.mp4
  video_001_visual.mp4
  video_001_script.json
  video_001_sub.srt
  video_001_sub.ass
  video_001_voice.mp3
  video_001_voice_normalized.wav
  video_001_voice_text.txt
  video_001_timeline.json
  video_001_log.json
  video_002.mp4
  video_003.mp4
  segment_scoring_report.json
  script_variants.json
  project_summary.json
```

Known limitations:

- Sample videos là dummy test pattern, chỉ dùng để kiểm tra pipeline kỹ thuật.
- `edge-tts` cần internet khi render thật. E2E tests không gọi TTS online.
- Gemini không bắt buộc cho test offline vì script variants có fallback theo style.
- Pipeline chưa có AI vision hoặc scene detection nâng cao.

## Smart Segment Scoring

Sau khi tạo segment, backend sẽ sample tối đa 5 frame cho mỗi đoạn và tính các điểm cơ bản:

- `brightness_score`: tránh đoạn quá tối hoặc cháy sáng.
- `sharpness_score`: tránh đoạn quá mờ bằng variance of Laplacian.
- `motion_score`: ưu tiên chuyển động vừa phải.
- `freeze_score`: loại đoạn gần như đứng hình.
- `stability_score`: giảm ưu tiên đoạn rung hoặc chuyển động quá mạnh.

Kết quả được ghi vào:

```txt
segment_scoring_report.json
```

Timeline builder dùng weighted random theo `overall_score`, vì vậy segment điểm cao có xác suất được chọn cao hơn nhưng vẫn giữ seed để reproducible. Nếu số segment tốt quá ít, backend sẽ log warning và bổ sung segment điểm thấp hơn để batch không crash. Nếu không có segment nào dùng được sau scoring, job fail rõ với message `No usable video segments after scoring`.

## Timeline Templates

Timeline hiện được dựng theo template sản phẩm thay vì ghép random hoàn toàn. Template mặc định là:

```txt
ugc_reviewer_natural
```

Các template có sẵn:

- `product_showcase_clean`: showcase sản phẩm rõ, sạch, ưu tiên shot sáng và ổn định.
- `ugc_reviewer_natural`: review tự nhiên, nhịp vừa.
- `fast_tiktok_recut`: nhịp nhanh cho TikTok/Reels.
- `problem_solution`: cấu trúc vấn đề -> giải pháp.

Config có thể chọn template:

```json
{
  "timeline": {
    "template_id": "ugc_reviewer_natural"
  }
}
```

Mỗi output sẽ có thêm `video_XXX_timeline.json`, gồm template id, slot name, text role, score segment và tags của từng clip. Log output cũng ghi `timeline_template`, `average_segment_score` và `source_diversity` để debug.

## Script Variant Generator

Khi full batch không có custom script được lưu từ preview editor, backend sẽ tạo trước một danh sách script riêng cho từng output bằng `ScriptVariantGenerator`. Mỗi output có `output_index` riêng, prompt riêng và variant style riêng để tránh việc cả batch dùng chung một hook/CTA.

Các style mặc định:

- `problem_hook`: hook dạng nêu vấn đề.
- `reviewer_natural`: hook như người dùng review tự nhiên.
- `benefit_first`: đi thẳng vào lợi ích chính.
- `use_case_scene`: mở bằng tình huống sử dụng.
- `fast_sales`: hook ngắn, nhanh cho TikTok/Reels.
- `comparison_soft`: so sánh nhẹ, không công kích.

Nếu timeline template khớp `best_for_templates`, planner sẽ ưu tiên style phù hợp trước. Nếu số output nhiều hơn số style, planner xoay vòng nhưng tránh dùng cùng style ở hai video liên tiếp khi có thể.

File tổng được ghi tại:

```txt
script_variants.json
```

Mỗi video vẫn có file script riêng:

```txt
video_001_script.json
video_002_script.json
```

Nếu Gemini lỗi ở một output, backend tạo fallback theo đúng style của output đó thay vì dùng một script mock chung cho toàn batch. Nếu project có custom script đã lưu, custom script vẫn được ưu tiên theo logic editor hiện tại.

API hỗ trợ kiểm tra/generate trước:

```txt
GET  /api/script-variants/styles
POST /api/projects/{project_id}/generate-script-variants
```

## QA Và Log

Mỗi output có file log riêng:

```txt
video_001_log.json
```

Log gồm:

- `started_at`
- `finished_at`
- `duration_seconds`
- `steps`
- `warnings`
- `errors`
- `qa`

Status output:

- `success`: render và QA đạt.
- `warning`: video vẫn xuất được nhưng có cảnh báo, ví dụ TTS fallback hoặc duration lệch nhẹ.
- `failed`: lỗi bắt buộc, ví dụ final video không tạo được, file rỗng, ffprobe không đọc được, thiếu segment.

## Debug Lỗi FFmpeg

Kiểm tra FFmpeg:

```powershell
ffmpeg -version
ffprobe -version
```

Nếu PowerShell không nhận lệnh:

```powershell
where ffmpeg
where ffprobe
```

Cách sửa:

- Cài FFmpeg bằng `winget install Gyan.FFmpeg`.
- Mở terminal mới sau khi cài.
- Thêm thư mục `bin` của FFmpeg vào `PATH`.
- Hoặc set `AUTO_TOOL_FFMPEG_DIR`.

Nếu chạy exe và auto-install lỗi, xóa file zip hỏng rồi mở lại:

```powershell
Remove-Item "$env:LOCALAPPDATA\AutoTool\tools\ffmpeg\ffmpeg-release-essentials.zip" -Force
```

## Debug Lỗi Gemini

Kiểm tra key:

```powershell
$env:GEMINI_API_KEY
$env:GEMINI_API_KEYS
```

Hoặc kiểm tra key nhập trên UI.

Nếu Gemini trả invalid JSON:

- Xem `video_XXX_log.json`.
- Xem step `generate_script`.
- Xem `script_variants.json` để biết output nào dùng style nào và hook nào.
- Giảm độ dài mô tả/features quá dài.
- Kiểm tra model name trong config.
- Thử key khác.
- Tạm bật fallback khi debug:

```powershell
$env:AUTO_TOOL_ALLOW_SCRIPT_FALLBACK="1"
```

## Debug Lỗi TTS

Mặc định TTS dùng Edge TTS, sau đó tự fallback qua Piper, gTTS và silent nếu provider trước lỗi:

```txt
vi-VN-HoaiMyNeural
```

Nếu không nghe tiếng Việt hoặc voice không được tạo:

- Kiểm tra internet vì `edge-tts` cần gọi dịch vụ online.
- Kiểm tra `AUTO_TOOL_TTS_VOICE`.
- Nếu dùng Piper, kiểm tra `PIPER_MODEL_PATH`, `PIPER_CONFIG_PATH` và binary `piper` trong `PATH`.
- Xem warnings trong `video_XXX_log.json`.
- Backend retry Edge TTS theo `AUTO_TOOL_TTS_RETRIES`, tối đa 5 lần, rồi thử provider fallback.

- Test nhanh pipeline bằng silent mode:

```powershell
$env:AUTO_TOOL_TTS_PROVIDER="silent"
```

Nếu silent mode đang bật, output có thể có warning liên quan audio nhưng không nhất thiết fail job.

## Testing TTS

Tạo thử một file voice riêng trước khi render:

```powershell
cd backend
py -m app.tools.test_tts --provider edge_tts --voice vi-VN-HoaiMyNeural --text "Xin chào, đây là video review sản phẩm." --output ../examples/outputs/test_voice.mp3
```

Google Cloud TTS:

```powershell
$env:GOOGLE_TTS_CREDENTIALS_JSON_PATH="D:\Keys\google-tts-service-account.json"
py -m app.tools.test_tts --provider google_cloud_tts --voice vi-VN-Wavenet-A --text "Xin chào, đây là video review sản phẩm." --output ../examples/outputs/google_voice.mp3
```

Provider hỗ trợ:

- `edge_tts`: cần internet, chất lượng voice tiếng Việt tốt nhất trong MVP.
- `google_cloud_tts`: Google Cloud Text-to-Speech, cần service account/OAuth credentials và Text-to-Speech API đã bật trong Google Cloud project.
- `piper`: dùng model local, exe sẽ tự tải model `vi_VN-vais1000-medium` khi mở lần đầu.
- `gtts`: backup online.
- `silent`: chỉ để pipeline không crash khi cần debug.

Command sẽ in JSON gồm provider thực tế, `output_path`, `duration`, `format` và `warnings`.

## Audio Normalization

Trước khi mux vào video, Auto Tool normalize mọi voice provider về WAV 44.1kHz mono:

```txt
video_001_voice.mp3
video_001_voice_normalized.wav
```

Edge TTS/gTTS thường xuất MP3, Piper thường xuất WAV. Renderer luôn dùng file normalized để tránh lỗi mux audio không đồng nhất.

## Subtitle Sync Behavior

Subtitle được tạo theo duration voice thật:

- Voice ngắn hơn video quá 2 giây: log warning `voice_shorter_than_video`, video vẫn giữ đủ duration và phần cuối im lặng.
- Voice dài hơn video quá 1 giây: log warning `voice_longer_than_video`, final render cắt voice theo duration video.
- Subtitle cuối luôn bị clamp trước cuối video ít nhất 0.1 giây.

## Overlay & Subtitle Style Presets

Backend có thư viện preset style cho overlay và subtitle tại:

```txt
backend/app/modules/visual_style/
```

Các preset mặc định:

- `clean_review_light`
- `cute_pastel_shop`
- `tech_dark_neon`
- `beauty_soft_glow`
- `food_warm_label`
- `sale_bold_red`
- `fashion_minimal`
- `transparent_caption_box`

Config project có thêm:

```json
{
  "visual_style": {
    "preset_id": "clean_review_light",
    "custom_overrides": null
  }
}
```

Khi render, backend tạo thêm:

```txt
video_001_overlay.png
video_001_sub.ass
```

Pipeline sẽ ưu tiên burn overlay PNG + subtitle ASS. Nếu ASS hoặc overlay style lỗi, render không crash toàn batch; backend fallback về drawbox/SRT cũ và ghi warning trong `video_001_log.json`.

API style:

```txt
GET  /api/visual-styles
POST /api/visual-styles/preview
PUT  /api/projects/{project_id}/visual-style
```

Frontend hiển thị style selector ở Simple mode và Advanced mode trong trang render settings. Simple video style tự map sang preset subtitle/overlay phù hợp:

- `ugc_reviewer_natural` -> `clean_review_light`
- `product_showcase_clean` -> `transparent_caption_box`
- `fast_tiktok_recut` -> `sale_bold_red`
- `problem_solution` -> `clean_review_light`

## Crop Safety & Product Visibility Guard

Crop Safety Guard là lớp kiểm tra rule-based trước khi render visual. Backend sample một vài frame trong mỗi clip, tính saliency theo lưới, ước lượng rủi ro nội dung quan trọng nằm sát mép hoặc sát vùng overlay đáy, rồi gắn crop metadata vào timeline.

Các mode hiện có:

- `auto_safe`: mặc định. Smart crop theo vùng nổi bật, tự dùng nền mờ khi video ngang có nguy cơ mất chi tiết hai bên.
- `center_crop`: crop giữa truyền thống, dùng khi muốn kết quả nhất quán và không cần bảo vệ sát mép.
- `fit_blur_background`: luôn giữ full frame bằng nền mờ phía sau, hữu ích cho video ngang hoặc video quay sản phẩm sát mép.

Config:

```json
{
  "crop_safety": {
    "enabled": true,
    "mode": "auto_safe",
    "allow_blur_background": true,
    "reduce_zoom_on_risk": true,
    "reduce_overlay_on_risk": true
  }
}
```

Khi render, backend ghi:

```txt
crop_safety_report.json
video_001_log.json -> crop_safety
video_001_timeline.json -> crop_mode, crop_box, crop_safety_score
```

API đọc báo cáo mới nhất:

```txt
POST /api/projects/{project_id}/crop-safety/analyze
```

Frontend hiển thị checkbox Crop Safety trong Simple Mode, panel chi tiết trong Advanced Mode và báo cáo sau khi render preview. Đây là heuristic kỹ thuật, không phải AI nhận diện sản phẩm 100%; vẫn nên xem preview trước khi render full batch.

## Product Info Import

Auto Tool hỗ trợ import và chuẩn hóa thông tin sản phẩm trước khi tạo script. Tính năng này giúp người dùng không phải nhập thủ công toàn bộ form khi đã có mô tả sản phẩm từ shop, file nội bộ hoặc nội dung copy sẵn.

Supported Input Formats:

- Manual: nhập trực tiếp bằng form như cũ.
- Paste text/TXT: dán mô tả sản phẩm dạng nhiều dòng.
- JSON: hỗ trợ alias như `name`, `product_name`, `ten_san_pham`, `brand_name`, `benefits`, `specifications`.
- CSV: hỗ trợ header đơn giản như `name,brand,description,features,cta`; MVP chỉ lấy dòng đầu tiên.

Backend API:

```txt
POST /api/product-info/import
PUT  /api/projects/{project_id}/product-info
```

Ví dụ request import:

```json
{
  "input_type": "text",
  "raw_text": "Máy Chiếu 4K Android KAW XMAX10\nThương hiệu: KAW\nĐộ sáng 10.000 Lumens\nHỗ trợ 4K\nAndroid 9.0"
}
```

Kết quả import sẽ trả về:

- Tên sản phẩm, thương hiệu, mô tả ngắn.
- Điểm nổi bật đã làm sạch.
- Thông số được cung cấp rõ ràng.
- CTA.
- Ngành hàng gợi ý.
- Hashtag gợi ý.
- Claim risk warnings.
- Missing fields.
- Confidence score.

Product Validation:

- Error nếu thiếu `name`.
- Error nếu thiếu cả `description` và `features`.
- Warning nếu thiếu `brand`, `cta` hoặc ngành hàng.
- Warning nếu có claim mạnh như `tốt nhất`, `số 1`, `100% hiệu quả`, `chữa bệnh`, `hết mụn`, `trắng bật tông`.
- Với ngành mỹ phẩm, mẹ và bé, đồ ăn/uống, validator cảnh báo kỹ hơn với claim sức khỏe/làm đẹp.

Lưu ý pháp lý: Auto Tool chỉ chuẩn hóa thông tin dựa trên nội dung người dùng cung cấp. Tool không tự xác minh thông số sản phẩm, không crawl website, không tự bịa claim và không tạo thông số mới. Người dùng cần kiểm tra lại nội dung trước khi render hoặc đăng video quảng cáo.

Khi product có `specs`, script prompt sẽ nhận thêm:

```txt
Thông số được cung cấp:
- Độ sáng: 10.000 Lumens
- Hệ điều hành: Android 9.0
```

Gemini/script generator chỉ được dùng specs trong danh sách này và không được tự bịa thông số kỹ thuật mới.

## Product Info QA Và Script Safety Guard

Auto Tool có thêm lớp kiểm tra rule-based trước khi render và sau khi tạo script để giảm rủi ro nội dung sai thông tin sản phẩm.

API:

```txt
POST /api/projects/{project_id}/safety-check
```

Safety Guard kiểm tra:

- Product info có thiếu tên, mô tả hoặc điểm nổi bật không.
- Claim rủi ro như `tốt nhất`, `số 1`, `100% hiệu quả`, `chữa bệnh`, `hết mụn`, `trắng bật tông`.
- Ngành nhạy cảm như mỹ phẩm, đồ ăn/uống, mẹ và bé có claim sức khỏe/làm đẹp quá mạnh không.
- Script còn placeholder như `{product_name}`, `{brand}`, `{feature}`, `CTA:`, `Hook:` không.
- Script có bịa thông số kỹ thuật ngoài product info không, ví dụ `pin 5000mAh`, `IPX7`, `Bluetooth 5.0`, `UPF`, `Lumens`.
- Caption có rỗng/quá dài/claim mạnh không.
- Hashtag có quá nhiều, thiếu `#`, có khoảng trắng hoặc lệch ngành rõ ràng không.

Render Blocking Rules:

- Error sẽ chặn render preview/full batch.
- Warning không chặn render nhưng được ghi vào job log, `project_summary.json` hoặc `video_001_log.json`.
- Nếu script generated có error, tool thử dùng fallback script an toàn trước khi render tiếp.

Log output:

```json
{
  "safety_check": {
    "passed": true,
    "warnings_count": 1,
    "errors_count": 0,
    "issues": []
  }
}
```

Mỗi video log có thêm:

```json
{
  "script_safety": {
    "passed": true,
    "warnings_count": 0,
    "errors_count": 0,
    "issues": [],
    "fallback_used": false
  }
}
```

Safety Guard chỉ là lớp kiểm tra rule-based để giảm rủi ro nội dung sai. Nó không thay thế việc người dùng kiểm tra thông tin sản phẩm, claim quảng cáo và quy định nền tảng trước khi đăng.

## Industry Preset Pack

Auto Tool có Industry Preset Pack để gợi ý cấu hình theo ngành hàng sản phẩm. Preset ngành chỉ là điểm bắt đầu; người dùng vẫn nên render preview và chỉnh lại từng setting trước khi render full batch.

Supported Product Categories:

- `general_product`: Sản phẩm tổng quát.
- `tech_electronics`: Công nghệ / Điện tử.
- `beauty_cosmetics`: Mỹ phẩm / Làm đẹp.
- `fashion_accessories`: Thời trang / Phụ kiện.
- `home_lifestyle`: Gia dụng / Tiện ích nhà cửa.
- `mom_baby`: Mẹ và bé.
- `food_beverage`: Đồ ăn / Đồ uống.
- `fast_sale_trending`: Sale nhanh / Sản phẩm trend.

Industry preset ảnh hưởng các nhóm setting sau:

- Video style và timeline template.
- Mức độ chỉnh sửa.
- Overlay/subtitle visual style.
- Giọng đọc TTS.
- Script variation và preferred script styles.
- Caption tone và hashtag gợi ý.

API:

```txt
GET /api/industry-presets
GET /api/industry-presets/{preset_id}
PUT /api/projects/{project_id}/industry-preset
```

Config project có thêm:

```json
{
  "industry": {
    "preset_id": "tech_electronics"
  },
  "script_variation": {
    "mode": "auto_mix",
    "preferred_variant_ids": ["benefit_first", "reviewer_natural", "use_case_scene"]
  }
}
```

Trong Simple Mode, chọn ngành hàng sẽ tự set các gợi ý chính nhưng người dùng vẫn override được từng field. Trong Advanced Mode, người dùng chọn preset và bấm Apply để áp dụng lại; nếu muốn quay về cấu hình an toàn thì dùng `general_product`.
- Tool không dùng `atempo` để ép voice dài khớp video, tránh giọng bị nhanh/chậm bất thường.

Mỗi `video_001_log.json` có thêm block `tts` và `subtitle_sync` để debug provider, raw voice, normalized voice và active subtitle duration.

## Output Quality Review

Sau khi render full batch, mở Result page và bấm `Review Output Quality`.

Backend sẽ đọc các file log sẵn có của từng output:

```txt
video_001_log.json
video_001_timeline.json
video_001_sub.ass
project_summary.json
```

Tool tính điểm kỹ thuật cho từng video:

- Technical: file final, ffprobe, duration, resolution, audio/video stream.
- Segment: average segment score, source diversity, cảnh bị lặp liên tục.
- Audio: TTS provider, silent fallback, voice duration lệch video.
- Subtitle: file subtitle, warning subtitle, subtitle burn fallback.
- Timeline: template id, slot name, text role metadata.

Overall score:

```txt
technical 30% + segment 25% + audio 20% + subtitle 15% + timeline 10%
```

Quality score chỉ là đánh giá kỹ thuật dựa trên log/render metadata. Nó không thay thế việc người dùng xem video bằng mắt.

Review được lưu ở:

```txt
output_quality_review.json
```

và lưu trong SQLite để giữ trạng thái người dùng đánh dấu `Good`, `Bad`, `Need Rerender` hoặc `Ignored`.

## Rerender Failed/Selected Videos

Từ trang Output Quality Review, người dùng có thể render lại một phần batch:

- `Rerender Selected`: chỉ render các video đang tick.
- `Rerender Failed`: chỉ render output lỗi.
- `Rerender Needs Rerender`: render các output bị score thấp hoặc người dùng đánh dấu cần render lại.

Default rerender options:

```txt
reuse_script: true
reuse_timeline: false
reuse_settings: true
```

Output cũ không bị xóa. Output mới nằm trong:

```txt
outputs/rerenders/run_001/
  video_003.mp4
  video_003_script.json
  video_003_sub.srt
  video_003_voice.mp3
  video_003_timeline.json
  video_003_log.json
  rerender_summary.json
```

Sau khi rerender, review endpoint sẽ ưu tiên file mới nhất theo output index nhưng vẫn giữ file cũ trên ổ đĩa.

## Common TTS Issues

- Edge TTS lỗi: kiểm tra mạng, voice name và thử lại.
- Piper lỗi: kiểm tra model local hoặc mở lại exe để app tự cài vào `%LOCALAPPDATA%\AutoTool\tools\piper`.
- gTTS lỗi: thường do mạng hoặc giới hạn dịch vụ.
- Silent fallback: không phải voice thật, chỉ để batch render không crash.

## Checklist Trước Khi Render

- Source folder tồn tại và có video hợp lệ.
- Video nguồn dài hơn 3 giây.
- FFmpeg và FFprobe chạy được.
- Output folder có quyền ghi.
- Gemini API key đã nhập hoặc fallback đã bật khi debug.
- Product name, description, features và CTA không rỗng.
- Duration phù hợp với số lượng video nguồn.
- Resolution là `1080x1920`.
- Music folder/file tồn tại nếu bật nhạc nền.
- Render preview trước khi render full batch.
- Kiểm tra Crop Safety score/cảnh báo sau preview, đặc biệt với video ngang hoặc sản phẩm sát mép.
- Xem lại script/subtitle sau preview.
- Nếu render full batch không dùng custom script, kiểm tra `script_variants.json`.
- Kiểm tra warning/error trong Result page.

## Roadmap

- Smart Segment: chọn segment theo chuyển động, độ nét, scene boundary và audio cue.
- Product-aware Timeline: ưu tiên đoạn có sản phẩm rõ, tránh đoạn mờ/không liên quan.
- Better Script Editor: form chỉnh từng dòng voiceover/subtitle thay vì JSON textarea.
- Asset Overlay: thay overlay chữ bằng ảnh/template overlay.
- Voice Provider thật có kiểm soát tốc độ, emotion và caching.
- Render Queue ổn định hơn với cancel/retry job.
- File manager local để mở output folder từ UI.
- Preset nâng cao theo ngành hàng.
- Export project package để chuyển máy.
- Bộ test tự động cho renderer/QA/API.

## Tài Liệu Khác

- [Development Plan](docs/DEVELOPMENT_PLAN.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Backend README](backend/README.md)
- [Frontend README](frontend/README.md)

## Content Manager / Caption Export

Sau khi render xong full batch, người dùng có thể mở trang `Quản lý caption` từ trang kết quả để quản lý nội dung đăng bài cho từng video.

Backend đọc output mới nhất của project, lấy thông tin từ `video_XXX_script.json`, `video_XXX_timeline.json` và kết quả render trong SQLite để tạo danh sách content item. Nếu người dùng đã sửa caption, hashtag, CTA, ghi chú hoặc trạng thái đăng bài thì các giá trị này được giữ lại khi build lại danh sách.

API chính:

```txt
GET  /api/projects/{project_id}/content
PUT  /api/projects/{project_id}/content/{output_index}
POST /api/projects/{project_id}/content/{output_index}/mark-copied
POST /api/projects/{project_id}/content/{output_index}/mark-posted
POST /api/projects/{project_id}/content/export
```

Các trạng thái publish:

- `draft`: nội dung mới tạo, chưa dùng.
- `copied`: người dùng đã copy caption/hashtag.
- `posted`: người dùng đã đánh dấu đã đăng.
- `skipped`: bỏ qua video này.

File export được ghi vào output folder mới nhất:

```txt
content_items.json
content_export.json
content_export.csv
content_export.txt
content_plan.md
```

`content_export.csv` dùng UTF-8 BOM để mở ổn định trong Excel. `content_plan.md` dùng để review nhanh kế hoạch đăng bài.

---

## Release Candidate Testing (v0.1.0-rc1)

Auto Tool hiện đang ở trạng thái **Release Candidate v0.1.0-rc1**.

### Phiên bản

```txt
0.1.0-rc1
```

Kiểm tra phiên bản qua API:

```txt
GET http://localhost:8000/api/health
→ { "status": "ok", "version": "0.1.0-rc1" }
```

Hoặc xem ở footer giao diện web.

---

## Smoke Test

Smoke test kiểm tra pipeline end-to-end nhanh — **không cần video thật**, **không cần internet** (mock mode mặc định):

```powershell
cd backend
py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json
```

Output mẫu khi thành công:

```json
{
  "status": "success",
  "steps": {
    "load_config": "ok",
    "check_env": "ok",
    "scan": "ok",
    "segment": "ok",
    "segment_scoring": "ok",
    "timeline": "ok",
    "script": "ok",
    "tts": "ok",
    "subtitle": "ok",
    "render_preview": "ok",
    "qa": "ok"
  },
  "preview_path": "..."
}
```

Test với video thật (cần bỏ video vào `examples/sample_videos/projector/`):

```powershell
py -m app.tools.smoke_test --config ../examples/qa_projects/projector_config.json --no-mock
```

---

## Manual QA

Template báo cáo QA thủ công:

```txt
docs/MANUAL_QA_REPORT_TEMPLATE.md
```

Checklist đầy đủ:

```txt
docs/RELEASE_QA_CHECKLIST.md
```

Config mẫu cho 3 sản phẩm QA:

```txt
examples/qa_projects/
  projector_config.json
  fan_config.json
  jacket_config.json
  README.md
```

---

## Performance Logs

Sau mỗi render, Auto Tool ghi chi tiết thời gian từng bước vào `video_XXX_log.json`:

```json
{
  "performance": {
    "render_visual_seconds": 18.4,
    "script_seconds": 3.1,
    "tts_seconds": 2.8,
    "subtitle_seconds": 0.1,
    "render_final_seconds": 7.6,
    "total_seconds": 38.7
  }
}
```

Và tổng kết toàn batch trong `project_summary.json`:

```json
{
  "performance_summary": {
    "total_runtime_seconds": 180.5,
    "average_time_per_video": 36.1,
    "slowest_step": "render_visual",
    "slowest_output_index": 3,
    "cache_saved_estimated_seconds": 38.0
  }
}
```

---

## Performance Cache

Auto Tool dùng file-based cache để render preview/rerender nhanh hơn khi input chưa thay đổi. Cache nằm trong:

```txt
outputs/{project_name}/.cache/
  media_metadata/
  segment_scores/
  crop_safety/
  scripts/
  tts/
  overlays/
```

Các bước đang được cache:

- Video metadata từ `ffprobe`.
- Segment scoring result.
- Crop safety analysis.
- Script variants theo product/render/timeline settings.
- TTS voice file theo text, provider, voice, rate và duration.
- Overlay asset theo style preset và resolution.
- Style preview image theo preset, resolution và sample text.

Cache key có tính đến đường dẫn file, dung lượng file, modified time và config liên quan. Nếu video nguồn thay đổi nội dung hoặc thời gian sửa file, metadata/score/crop cache cũ sẽ không được dùng.

Config mẫu:

```json
{
  "cache": {
    "enabled": true,
    "cache_media_metadata": true,
    "cache_segment_scoring": true,
    "cache_crop_safety": true,
    "cache_tts": true,
    "cache_overlay_assets": true,
    "clear_cache_before_render": false
  }
}
```

API cache:

```txt
GET  /api/projects/{project_id}/cache/summary
POST /api/projects/{project_id}/cache/clear
```

Frontend có panel `Performance Cache` trong trang Render Settings để xem cache hit/miss, dung lượng cache và xoá cache. Nếu nghi output bị ảnh hưởng bởi cache cũ, bấm `Xoá cache` rồi render lại. Cache JSON bị hỏng sẽ được bỏ qua và pipeline sẽ chạy lại bước tương ứng, không làm crash batch.

`project_summary.json` có thêm:

```json
{
  "cache_summary": {
    "enabled": true,
    "hits": 42,
    "misses": 18,
    "cache_size_mb": 245.7,
    "media_metadata_hits": 5,
    "segment_score_hits": 20,
    "crop_safety_hits": 12,
    "tts_hits": 3,
    "overlay_hits": 2
  }
}
```

Mỗi `video_001_log.json` có block:

```json
{
  "cache": {
    "segment_score_cache_hits": 6,
    "crop_safety_cache_hits": 6,
    "tts_cache_hit": true,
    "overlay_cache_hit": true
  }
}
```

---

## Source Media Manager

Source Media Manager cho phép kiểm soát video nguồn và segment trước khi render full batch. Luồng sử dụng:

```txt
1. Tạo project
2. Scan video nguồn
3. Mở Source Media Manager
4. Exclude video nguồn xấu
5. View segments của video còn lại
6. Đánh dấu segment đẹp là Favorite hoặc Good
7. Exclude/Bad các segment không muốn dùng
8. Render preview/full batch
```

API:

```txt
GET  /api/projects/{project_id}/source-media
PUT  /api/projects/{project_id}/source-media/review
GET  /api/projects/{project_id}/segments
PUT  /api/projects/{project_id}/segments/{segment_id}/review
POST /api/projects/{project_id}/segments/bulk-review
```

Config:

```json
{
  "source_media": {
    "respect_user_exclusions": true,
    "prefer_favorite_segments": true,
    "allow_excluded_fallback": false
  }
}
```

Quy tắc render:

- Video hoặc segment được đánh dấu `excluded` hoặc `bad` sẽ không được dùng khi render.
- Segment `favorite` hoặc `good` được ưu tiên khi dựng timeline.
- Segment `pending` vẫn được dùng nếu quality score đủ tốt.
- Favorite segment có score kỹ thuật quá thấp vẫn được phép dùng, nhưng log warning `favorite_segment_has_low_quality_score`.
- Tool không dùng lại excluded segment trừ khi `allow_excluded_fallback=true`.

Review status được lưu trong SQLite để API đọc nhanh và đồng thời backup ra:

```txt
source_media_reviews.json
segment_reviews.json
```

Render output có thêm:

```json
{
  "source_media_summary": {
    "total_media": 8,
    "excluded_media": 1,
    "total_segments": 120,
    "segments_after_user_filter": 76,
    "favorite_segments_used": 4
  }
}
```

Mỗi `video_001_log.json` có `source_media_filter`, còn `video_001_timeline.json` có `user_review_status` và `source_media_review_status` ở từng clip để debug vì sao timeline chọn segment đó.

Source Media Manager không xoá file gốc, không tải video từ nền tảng khác, không chỉnh sửa watermark và không thay thế việc người dùng kiểm tra quyền sử dụng media.

---

## Product Assets From Draft

Chrome Extension có thể gửi image URLs đang hiển thị trên trang sản phẩm Shopee vào Product Draft. Auto Tool không tự crawl thêm ảnh của shop và không tải hàng loạt. Ảnh chỉ được lưu local khi người dùng chọn trong Import Inbox.

Luồng sử dụng:

```txt
1. Mở Shopee product bằng Chrome Extension và gửi draft vào Auto Tool
2. Vào Import Inbox và mở draft
3. Trong Product Assets, chọn ảnh muốn dùng
4. Bấm Import Assets để tải ảnh đã chọn về local
5. Đặt role cho ảnh: main_product, reference, poster, thumbnail, description, variation, unused
6. Khi Create Project from Draft, attach selected assets vào project
7. Vào Render Settings hoặc /projects/{project_id}/assets để quản lý ảnh đã attach
```

API:

```txt
GET    /api/product-drafts/{draft_id}/assets
POST   /api/product-drafts/{draft_id}/assets/import
POST   /api/product-drafts/{draft_id}/assets/attach-to-project/{project_id}
GET    /api/projects/{project_id}/assets
PUT    /api/product-assets/{asset_id}
DELETE /api/product-assets/{asset_id}
GET    /api/product-assets/{asset_id}/file
```

Ảnh draft chưa có project được lưu ở data app local:

```txt
data/imported_assets/drafts/{draft_id}/
```

Ảnh đã attach vào project được lưu ở:

```txt
{output_folder}/{project_name}/assets/product/
```

Auto Tool chỉ chấp nhận tải `image/jpeg`, `image/png`, `image/webp`, giới hạn 15MB mỗi ảnh. Người dùng cần tự đảm bảo có quyền sử dụng hình ảnh cho mục đích của mình.

---

## Product Reference Prompt Pack

Prompt Pack dùng product info, specs/features, industry preset, visual style, timeline template và Product Assets đã chọn để tạo bộ prompt tham chiếu sản phẩm. Chức năng này chỉ tạo nội dung prompt/storyboard/export text, không gọi AI video model, không gọi image generation model, không chỉnh sửa ảnh bằng AI và không tự đăng video.

Luồng sử dụng:

```txt
1. Extension gửi Product Draft từ Shopee vào Import Inbox
2. User import ảnh sản phẩm vào project
3. User đặt một ảnh là Main Product trong Product Assets
4. Vào /projects/{project_id}/prompt-pack
5. Chọn duration 8s hoặc 10s, scene count 5, model hint
6. Bấm Generate Prompt Pack
7. Tool tạo Product Reference Summary, Accuracy Lock, Storyboard, Full Prompt, Negative Prompt và JSON Prompt
8. User copy prompt để dùng ở AI video/image model bên ngoài
```

Files được export vào:

```txt
{output_folder}/{project_name}/prompt_pack/
```

Gồm:

```txt
product_reference_summary.json
storyboard_5_scenes.json
video_prompt_full.txt
video_prompt_short.txt
video_prompt_pack.json
negative_prompt.txt
prompt_pack_generation_log.json
```

API:

```txt
POST /api/projects/{project_id}/reference-summary
POST /api/projects/{project_id}/storyboard
POST /api/projects/{project_id}/video-prompt-pack
```

Prompt Accuracy Lock nhắc model giữ đúng tên sản phẩm, thương hiệu, màu sắc, form dáng, logo, chi tiết vật lý và chỉ dùng claim đã có trong product info/specs. Nếu Safety Guard phát hiện warning, warning đó được đưa vào forbidden claims để giảm rủi ro prompt bịa hoặc nói quá sự thật.

Nếu project chưa có ảnh tham chiếu, Prompt Pack vẫn tạo được nhưng sẽ có warning: prompt chỉ dựa trên text nên độ chính xác hình ảnh có thể thấp hơn.

---

## Known Limitations (v0.1.0-rc1)

Những hạn chế cố ý trong phiên bản này — **không nằm trong scope RC v0.1**:

| Hạn chế | Giải thích |
|---------|------------|
| Không tự tải video từ TikTok/Shopee | Phải bỏ video thủ công vào thư mục nguồn |
| Không tự đăng video lên mạng xã hội | Cần copy file video và đăng tay |
| Chất lượng video phụ thuộc video input | Garbage in, garbage out — cần video nguồn chất lượng |
| Edge TTS cần kết nối internet | Dùng Piper hoặc silent mode khi offline |
| Piper cần tải model local (cỡ ~60MB) | Exe tự tải lần đầu; cần internet lần đầu |
| Segment scoring chỉ là heuristic | Không phải AI vision — không nhận diện sản phẩm trong khung hình |
| Quality score chỉ là đánh giá kỹ thuật | Luôn xem video bằng mắt trước khi đăng |
| Gemini cần API key | Không có API key → script dùng style template mặc định |
| Chưa hỗ trợ multi-user | Dùng cho máy cá nhân, một người dùng |
| Chưa có cloud render | Render chạy trên máy local, cần CPU/GPU mạnh |
