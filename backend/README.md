# Auto Tool Backend MVP

Backend MVP cung cap CLI local de:

- Scan video dau vao bang `ffprobe`
- Tao segment, cham diem segment bang OpenCV/NumPy va build product-aware timeline theo template
- Render visual recut bang `ffmpeg`
- Viet script bang Gemini neu co API key
- Tao Script Variant rieng cho tung output, khong dung chung mot script cho ca batch
- Fallback script local neu Gemini loi hoac thieu API key
- Tao voiceover tieng Viet qua TTS provider system: Edge TTS -> Piper -> gTTS -> silent fallback
- Tao subtitle `.srt` de debug va `.ass` de burn vao video
- Burn overlay day video, subtitle, voice va nhac nen vao final video

Frontend local nam trong thu muc `../frontend`. Backend van khong lam auto download, auto post, watermark bypass, multi-provider AI hoac scene detection nang cao.

## Yeu Cau

- Python 3.10+
- FFmpeg va FFprobe. Neu khong co trong `PATH`, backend se tu tai FFmpeg Windows vao `%LOCALAPPDATA%\AutoTool\tools\ffmpeg` trong lan chay dau tien.
- Neu chay bang file exe, launcher cung tu tai Piper Windows va voice tieng Viet vao `%LOCALAPPDATA%\AutoTool\tools\piper` trong lan mo dau tien.
- OCR hard-sub mac dinh dung EasyOCR. Neu chua co, app tu cai package vao `%LOCALAPPDATA%\AutoTool\python_packages\pyXX` va EasyOCR tu tai model trong lan dau.
- NumPy va OpenCV cho Smart Segment Scoring.

### Cai FFmpeg Tren Windows

```powershell
winget install Gyan.FFmpeg
ffmpeg -version
ffprobe -version
```

Neu `ffmpeg` hoac `ffprobe` khong nhan lenh sau khi cai, mo terminal moi hoac them thu muc `bin` cua FFmpeg vao bien moi truong `PATH`.

Backend cung co the dung FFmpeg bundled/local bang bien moi truong:

```powershell
$env:AUTO_TOOL_FFMPEG_DIR="D:\Tools\ffmpeg\bin"
```

Neu muon tat auto-install:

```powershell
$env:AUTO_TOOL_AUTO_INSTALL="0"
```

## Cai Dependencies

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Cau Hinh Gemini

Gemini la bat buoc cho script/mac dinh. Moi output video se goi Gemini rieng voi `output_index` rieng de tao script/subtitle khac nhau theo prompt JSON co dinh. Neu khong co key hoac API loi, output do se fail ro rang thay vi am tham dung script mock.

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

Backend cung tu doc `.env` trong thu muc `backend`, project root hoac cung thu muc voi file exe:

```txt
GEMINI_API_KEY=your_api_key_here
```

Neu co nhieu key, co the nhap tren giao dien, moi dong mot key. Backend se thu key theo thu tu xoay vong theo `output_index`; neu key dang dung loi thi tu dong thu key tiep theo. Cung co the dat nhieu key bang env:

```txt
GEMINI_API_KEYS=key_1,key_2,key_3
```

Chi nen bat fallback local khi debug/offline:

```powershell
$env:AUTO_TOOL_ALLOW_SCRIPT_FALLBACK="1"
```

Model lay tu config:

```json
"ai": {
  "text_model": "gemini-3.1-flash-lite",
  "tone": "friendly_reviewer",
  "language": "vi"
}
```

## Cau Hinh TTS Tieng Viet

Backend co TTS provider system. Mac dinh:

```txt
primary: edge_tts
fallback: piper
backup: gtts
last fallback: silent
```

`edge_tts` la provider khuyen nghi cho voice tieng Viet online. Voice mac dinh:

```txt
vi-VN-HoaiMyNeural
```

Co the doi voice bang config project, UI Render Settings hoac bien moi truong:

```powershell
$env:AUTO_TOOL_TTS_VOICE="vi-VN-NamMinhNeural"
```

Neu `edge_tts` khong tao duoc file voice hop le, backend retry nhe theo `AUTO_TOOL_TTS_RETRIES` roi tu dong thu provider fallback. Gia tri retry toi da la 5:

```powershell
$env:AUTO_TOOL_TTS_RETRIES="5"
```

Piper la provider offline. Can cai binary `piper` trong PATH va khai bao model:

```powershell
$env:PIPER_MODEL_PATH="D:\Models\piper\vi_VN-vais1000-medium.onnx"
$env:PIPER_CONFIG_PATH="D:\Models\piper\vi_VN-vais1000-medium.onnx.json"
```

Model mac dinh cho auto setup Piper:

```txt
Language: vi_VN
Quality: medium
Samplerate: 22,050Hz
Model: vi_VN-vais1000-medium
```

Khi nguoi dung mo `AutoTool.exe`, app se tu setup Piper neu may chua co:

```txt
%LOCALAPPDATA%\AutoTool\tools\piper
%LOCALAPPDATA%\AutoTool\tools\piper\models
```

Sau khi tai xong, launcher tu set `PATH`, `PIPER_MODEL_PATH` va `PIPER_CONFIG_PATH` cho process dang chay. Neu nguoi dung khong biet code thi chi can mo exe; lan dau co the mat thoi gian tai binary/model, cac lan sau dung lai file da co.

gTTS la backup online khi Edge/Piper loi. Silent chi nen dung de test pipeline khi khong can voice that:

```powershell
$env:AUTO_TOOL_TTS_PROVIDER="silent"
```

Google Cloud TTS co the dung lam provider chinh neu da bat Text-to-Speech API trong Google Cloud project:

```powershell
$env:AUTO_TOOL_TTS_PROVIDER="google_cloud_tts"
$env:GOOGLE_TTS_CREDENTIALS_JSON_PATH="D:\Keys\google-tts-service-account.json"
$env:AUTO_TOOL_TTS_VOICE="vi-VN-Wavenet-A"
```

Google Cloud Text-to-Speech REST dùng OAuth/service account credentials. API key chỉ là fallback legacy và có thể bị Google từ chối.

Tren UI, chon `Google Cloud TTS`, nhap API key, bam `Load Google Voices`, sau do chon voice Google tra ve.

Config JSON co the khai bao:

```json
"tts": {
  "provider": "edge_tts",
  "fallback_provider": "piper",
  "voice": "vi-VN-HoaiMyNeural",
  "language": "vi",
  "api_key": null,
  "credentials_json_path": null,
  "access_token": null,
  "rate": "+0%",
  "pitch": "+0Hz",
  "volume": "+0%",
  "output_format": "mp3"
}
```

## Cau Hinh Overlay Va Subtitle

Overlay day mac dinh chiem khoang 1/3 chieu cao video, subtitle duoc can giua vung overlay:

```json
"overlay_height": 33,
"subtitle_size": 84
```

Subtitle va voiceover dung chung timeline theo cau hoan chinh: backend chi tach `voiceover` theo dau cau, tao TTS tung cau o toc do tu nhien, do duration that roi dung chinh duration do cho subtitle. Text co the xuong nhieu dong trong cung mot block subtitle, nhung khong bi cat thanh cac timing nho theo so tu.

Moi output video se generate script rieng theo `output_index`. Prompt Gemini va fallback script deu duoc scale theo `render.duration`, nen video 30 giay se tao nhieu doan voiceover/subtitle hon va timeline subtitle phu gan het video thay vi dung o moc 8-12 giay.

### Testing TTS

```powershell
cd backend
py -m app.tools.test_tts --provider edge_tts --voice vi-VN-HoaiMyNeural --text "Xin chao, day la video review san pham." --output ../examples/outputs/test_voice.mp3
```

Command in JSON gom provider thuc te, output path, duration, format va warnings. Co the doi `--provider` thanh `piper`, `gtts` hoac `silent`.

### Audio Normalization Va Subtitle Sync

Moi voice provider se duoc normalize ve WAV 44.1kHz mono truoc khi render final:

```txt
video_001_voice.mp3
video_001_voice_normalized.wav
```

Subtitle bam theo voice duration that:

- Voice ngan hon video qua 2 giay: warning `voice_shorter_than_video`, video van du duration va cuoi video im lang.
- Voice dai hon video qua 1 giay: warning `voice_longer_than_video`, final render cat voice theo video duration.
- Subtitle cuoi khong vuot qua `target_duration - 0.1`.
- Khong dung `atempo` de ep voice khop video, tranh giong doc bi nhanh/cham bat thuong.

## Script Variant Generator

Khi project khong co custom script tu preview editor, backend se generate truoc mot danh sach script variants cho toan batch:

```txt
script_variants.json
```

Moi output van co file script rieng:

```txt
video_001_script.json
video_002_script.json
```

Variant style mac dinh:

- `problem_hook`: hook neu van de, gan gui.
- `reviewer_natural`: hook nhu nguoi dung review tu nhien.
- `benefit_first`: vao loi ich chinh.
- `use_case_scene`: mo bang tinh huong su dung.
- `fast_sales`: hook nhanh cho TikTok/Reels.
- `comparison_soft`: so sanh nhe, khong cong kich.

Planner uu tien style phu hop voi `timeline.template_id`, sau do xoay vong neu `output_count` lon hon so style. Neu Gemini loi o mot output, output do dung fallback theo dung style dang chon, khong dung mot script mock chung cho ca batch.

API:

```txt
GET  /api/script-variants/styles
POST /api/projects/{project_id}/generate-script-variants
```

## Cau Hinh Nhac Nen

Nhac nen la optional. Dat file nhac vao:

```txt
examples/music
```

Sau do bat trong config:

```json
"music": {
  "enabled": true,
  "source_folder": "./music",
  "source_file": null,
  "volume": 0.12,
  "fade_in": 0.5,
  "fade_out": 0.8,
  "duck_under_voice": false
}
```

Neu muon dung mot file cu the, dat `source_file` thay vi `source_folder`.
Bat `duck_under_voice` neu muon nhac nho xuong trong luc voice dang doc.

Dinh dang ho tro:

- `.mp3`
- `.wav`
- `.m4a`
- `.aac`
- `.flac`
- `.ogg`
- `.opus`

Renderer se loop/trim nhac theo duration video, fade in/out va mix nho ben duoi voiceover. `volume` nen de khoang `0.08` den `0.18` de khong lan giong doc.

## Smart Segment Scoring

Sau khi `Segmenter` tao cac doan video, backend dung `SegmentScorer` de sample toi da 5 frame moi segment va tinh:

- `brightness_score`
- `sharpness_score`
- `motion_score`
- `freeze_score`
- `stability_score`
- `overall_score`

Reject rule MVP:

- `brightness_score < 0.25`: `too_dark_or_overexposed`
- `sharpness_score < 0.25`: `too_blurry`
- `freeze_score < 0.30`: `freeze_or_static`
- `overall_score < 0.40`: `low_quality_segment`

Segment khong bi xoa. Backend chi gan `is_rejected`, `reject_reasons` va `tags` nhu `bright`, `dark`, `sharp`, `blurry`, `high_motion`, `stable`.

Moi lan render se ghi report:

```txt
segment_scoring_report.json
```

Co the goi API rieng de xem summary truoc khi render:

```txt
POST /api/projects/{project_id}/analyze-segments
```

## Product-aware Timeline Templates

Timeline khong con ghep random hoan toan. Backend dung template co cau truc:

```txt
Hook -> Product -> Demo/Use Case -> Benefit -> CTA
```

Template mac dinh:

```txt
ugc_reviewer_natural
```

Template co san:

- `product_showcase_clean`
- `ugc_reviewer_natural`
- `fast_tiktok_recut`
- `problem_solution`

Config:

```json
"timeline": {
  "template_id": "ugc_reviewer_natural"
}
```

Moi slot uu tien segment theo `overall_score`, tag khop slot, source diversity va duration fit. Moi output tao them:

```txt
video_001_timeline.json
```

Log output co them `timeline_template`, `average_segment_score` va `source_diversity`. Frontend co selector Timeline Style va API danh sach template:

```txt
GET /api/timeline-templates
```

## Chay CLI

```powershell
cd backend
py -m app.main --config ../examples/product_config.example.json
```

Path tuong doi trong config duoc resolve theo vi tri file config. Voi config mau, source video mac dinh nam o:

```txt
examples/sample_videos/kaw_xmax10
```

Output duoc tao trong:

```txt
examples/outputs/{project_name}-{YYYY-MM-DD-HHMMSS}
```

Chay sample project co san video dummy:

```powershell
cd backend
py -m app.main --config ../examples/sample_project/product_config.example.json
```

Output sample nam trong:

```txt
examples/sample_project/outputs/{project_name}-{YYYY-MM-DD-HHMMSS}
```

## Chay Local API

CLI van duoc giu nguyen. De chay API local cho frontend:

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

Neu `uvicorn` chua co trong environment:

```powershell
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --port 8000
```

Health check:

```txt
GET http://localhost:8000/api/health
```

API dung SQLite local tai:

```txt
backend/data/autotool.db
```

Khi chay ban exe, database mac dinh nam tai:

```txt
%LOCALAPPDATA%\AutoTool\data\autotool.db
```

Co the override bang bien moi truong:

```powershell
$env:AUTO_TOOL_DB_PATH="D:\Projects\Auto-Tool\backend\data\autotool.db"
```

Khi tao project qua API, path tuong doi trong JSON duoc resolve theo nhieu base an toan: current working directory, project root, `examples`, backend folder va folder cua exe. Vi vay UI co the gui:

```txt
examples/sample_videos/kaw_xmax10
examples/outputs
examples/music
```

Neu API bao `No valid input videos found` trong khi folder co video, nguyen nhan thuong gap la process API khong tim thay `ffprobe`. Ban moi se khong nuot loi nay nua: scanner se bao thang loi FFmpeg/FFprobe va thu auto-install neu duoc phep.

### API Endpoints

```txt
GET  /api/health
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/scan
POST /api/projects/{project_id}/analyze-segments
POST /api/projects/{project_id}/render
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

Render API chay background thread don gian, khong dung Celery/Redis. Trong luc render, frontend co the poll:

```txt
GET /api/jobs/{job_id}
```

Ket qua output:

```txt
GET /api/jobs/{job_id}/results
```

Preview mode:

```json
POST /api/projects/{project_id}/render
{
  "preview_only": true
}
```

Preview chi render 1 video, duration toi da 8 giay va ghi vao:

```txt
{output_folder}/preview
```

File preview gom:

```txt
preview_001.mp4
preview_001_visual.mp4
preview_001_script.json
preview_001_sub.srt
preview_001_sub.ass
preview_001_voice.mp3
preview_001_voice_normalized.wav
preview_001_voice_text.txt
preview_001_log.json
```

Sau khi preview xong, frontend doc script moi nhat bang:

```txt
GET /api/projects/{project_id}/latest-script
```

Neu nguoi dung sua script, frontend luu bang:

```txt
PUT /api/projects/{project_id}/script
```

Khi render full batch, backend se dung custom script da luu neu project co custom script. Neu chua co custom script, moi output van goi Gemini/fallback nhu cu.

Neu muon xem truoc danh sach variant cho batch hien tai:

```json
POST /api/projects/{project_id}/generate-script-variants
{
  "output_count": 10,
  "timeline_template_id": "ugc_reviewer_natural"
}
```

Response tra ve summary ngan gom `output_index`, `variant_style_id` va `hook`. File chi tiet nam trong output folder duoi ten `script_variants.json`.

## Chay Mot Process Cho Ca UI Va API

Sau khi build frontend:

```powershell
cd frontend
npm install
npm run build
```

Co the chay launcher backend:

```powershell
cd backend
py -m app.launcher
```

Launcher se:

- Kiem tra/cai FFmpeg neu thieu
- Start FastAPI local
- Serve frontend build trong cung process
- Tu mo browser vao UI

## Dong Goi Windows EXE

Script build exe nam tai:

```powershell
.\packaging\build_windows_exe.ps1
```

Exe sinh ra tai:

```txt
backend\dist\AutoTool.exe
```

Khi nguoi dung mo exe, app se tu kiem tra FFmpeg. Neu may chua co, app tai FFmpeg vao `%LOCALAPPDATA%\AutoTool\tools\ffmpeg` mot lan, sau do cac lan sau dung lai.
Build script cung cai va bundle EasyOCR/Torch vao exe. Neu build khong bundle OCR hoac chay source code thieu package, startup se tu cai OCR vao `%LOCALAPPDATA%\AutoTool\python_packages\pyXX` trong background. Dat `AUTO_TOOL_AUTO_INSTALL_OCR=0` neu muon tat rieng OCR auto-install.

## Chay Frontend Local

Mo terminal rieng:

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Mac dinh frontend goi API tai:

```txt
VITE_API_BASE_URL=http://localhost:8000
```

## Output Moi Video

Vi du voi output dau tien:

```txt
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
script_variants.json
```

`video_001.mp4` la final video co visual recut, voiceover, overlay day, subtitle va nhac nen neu duoc bat. `video_001_visual.mp4` la ban visual trung gian truoc khi ghep voice/subtitle/music.

Moi lan chay cung tao:

```txt
segment_scoring_report.json
script_variants.json
project_summary.json
```

## Output Quality Review va Rerender

API ho tro review output sau khi render full batch:

```txt
GET /api/projects/{project_id}/outputs/review
PUT /api/projects/{project_id}/outputs/{output_index}/review
POST /api/projects/{project_id}/rerender
```

Quality score duoc tinh tu log co san, khong goi AI moi:

- Technical score: QA, ffprobe, duration, resolution, audio/video stream.
- Segment score: average segment score va source diversity trong timeline.
- Audio score: TTS provider, fallback, silent mode, voice duration.
- Subtitle score: subtitle file, warning subtitle, burn fallback.
- Timeline score: template id, slot name, text role metadata.

File review duoc ghi tai output folder moi nhat:

```txt
output_quality_review.json
```

Rerender khong xoa output cu. Output moi nam trong:

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

Mac dinh rerender se reuse script, build timeline moi va dung settings hien tai. Quality score chi la danh gia ky thuat dua tren metadata/log, nguoi dung van nen xem lai video that.

## End-to-End Acceptance Tests

Chay toan bo backend tests:

```powershell
cd backend
py -m pytest
```

Chay rieng E2E/acceptance tests:

```powershell
cd backend
py -m pytest tests/e2e -q
```

Nhom E2E tao video dummy bang FFmpeg trong thu muc tam, patch TTS de khong goi mang, sau do chay pipeline that qua:

```txt
scan -> segment -> scoring -> timeline -> script variants -> voice -> subtitle -> render -> QA -> logs
```

Expected output structure:

```txt
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
segment_scoring_report.json
script_variants.json
project_summary.json
```

Known limitations:

- Sample videos chi la dummy test pattern de kiem tra pipeline ky thuat.
- Render that voi `edge-tts` can internet.
- Gemini loi hoac thieu key thi script variants fallback theo style, khong dung AI vision.
- Chua co scene detection nang cao, auto download, auto post hay watermark bypass.

## Subtitle Quality Scoring

Subtitle Review tu dong tao `subtitle_quality_report.json` khi document duoc tao va refresh report sau khi sua subtitle. Module danh gia do dai, reading speed, duration, CJK con sot, markdown/JSON leak, ky tu la, OCR/ASR confidence, mismatch, repeated text va timestamp.

API:

```txt
GET  /api/subtitle-review/documents/{document_id}/quality
POST /api/subtitle-review/documents/{document_id}/quality/refresh
GET  /api/subtitle-review/documents/{document_id}/quality/flagged-lines
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/suggest-rewrite
```

Preset `safe_review` bat `auto_mark_low_quality_lines=true`. Score thap hoac critical se danh dau line la `needs_fix`; approve van duoc phep nhung response va UI se hien quality warning. Quality score chi la rule-based va OCR/ASR confidence chi la tin hieu can kiem tra, khong dam bao ban dich dung hoan toan.

## Subtitle Auto Shortener and Safe Rewrite

Module `subtitle_rewrite` tao 1-3 goi y rut gon cho tung dong, validate keyword/brand/so lieu/don vi/forbidden claim, tinh quality score du kien va luu suggestion vao SQLite. Gemini duoc dung khi co key; neu loi hoac `use_ai=false`, tool fallback sang rule-based shortener va gan warning.

```txt
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/rewrite-suggestions
POST /api/subtitle-review/documents/{document_id}/lines/{line_index}/apply-rewrite
POST /api/subtitle-review/documents/{document_id}/rewrite-flagged-lines
```

Apply suggestion cap nhat `edited_text`, `rewrite_history`, refresh quality report va ghi `subtitle_rewrite_log.json`. Bulk auto-apply chi chay khi suggestion khong co safety warning, ngan hon ban goc va score sau rewrite >= 0.85.

Known limitations:

- Rewrite suggestion khong dam bao dung 100%.
- AI co the goi y chua hoan hao; user van nen review truoc khi approve.
- OCR/ASR sai source co the lam rewrite sai theo.
- Rule-based fallback uu tien an toan va co the khong rut gon du manh.

## Final Output QA and Platform Export Pack

Douyin render tu dong tao `video_XXX_final_qa.json` sau moi output thanh cong. QA dung ffprobe va FFmpeg volumedetect de kiem tra file/readability, duration, vertical 9:16, resolution, FPS, codec, audio volume, file size, subtitle/overlay artifact va ASS safe zone. Batch co them `final_qa_summary.json` va summary `final_output_qa`.

```txt
POST /api/final-output-qa/check
POST /api/final-output-qa/jobs/{job_id}/check
POST /api/douyin-reup/jobs/{job_id}/export-pack
GET  /api/douyin-reup/jobs/{job_id}/export-pack
```

Export pack copy video final va cac subtitle/log/QA artifact duoc chon, tao `captions.txt`, `captions.csv`, `posting_checklist.md` va `export_manifest.json`. Ho tro profile `tiktok`, `instagram_reels`, `youtube_shorts`, `generic_vertical`.

Known limitations: QA chi la rule-based; checker chua OCR lai final video; profile nen tang chi la goi y local; tool khong auto post.

## Silent / Immersive Product Reup

Silent Mode xu ly video khong co loi thoai ro rang theo flow: speech detection -> visual segments -> OCR neu co chu Trung -> caption Viet -> review tuy chon -> voiceover tuy chon -> render -> Final QA -> Export Pack.

Release candidate: `Silent Mode v1.0.0-rc1`.

```powershell
python -m app.tools.silent_mode_v1_rc_test --config ../examples/silent_mode_v1_rc/configs/silent_v1_chill_immersive.json
```

Them `--mock-ocr --mock-tts` de test nhe, hoac `--auto-render --final-qa --export-pack` de chay day du. Runner tiep tuc batch khi mot video loi va tao `job_log.json`, `douyin_reup_summary.json`, `silent_mode_summary.json`.

```txt
POST /api/silent-reup/detect
POST /api/silent-reup/plan
POST /api/silent-reup/render
POST /api/silent-reup/one-click
```

Neu `faster-whisper` da cai, speech detector tu dong dung model `tiny` va VAD. Dat `AUTO_TOOL_SILENT_SPEECH_ASR=0` de chi dung audio-energy fallback; dat `AUTO_TOOL_SILENT_SPEECH_MODEL` de doi model. Subtitle Review luu `context_json` de giu plan, product context va settings; render sau approve se tao lai voiceover tu caption da sua.

Artifact chinh: `silent_reup_plan.json`, `silent_reup_log.json`, `*_silent_segments.json`, `*_voiceover_script.txt`, `*_voiceover_sub.srt`, voice audio va `video_XXX_final_qa.json`.

### Lightweight Visual Tagging

Sau scene classification va OCR, Silent pipeline gan tag rule-based theo product context, OCR, folder/file name, segment type va motion/brightness/sharpness. Moi segment luu `visual_tags`, primary industry/scene/action va confidence; plan luu report cung recommended industry/strategy.

Caption template uu tien segment primary industry, industry user chon, video recommendation, product context, roi fallback `general_product`. User co the sua tag trong plan preview va regenerate caption ma khong analyze video hoac OCR lai. Tag user co confidence `1.0`.

```txt
GET  /api/silent-reup/visual-tags/vocabulary
POST /api/silent-reup/plans/{plan_id}/visual-tags
GET  /api/silent-reup/plans/{plan_id}/visual-tags
PUT  /api/silent-reup/plans/{plan_id}/segments/{segment_id}/tags
POST /api/silent-reup/plans/{plan_id}/regenerate-captions
```

Regenerate options: `industry: "auto"`, `use_visual_tags`, `respect_user_tag_overrides`. Tagging chi la heuristic nhe, khong phai object detection/AI vision; user van nen review tag va caption.

Known limitations: caption visual van la rule/template-based; OCR chi co ich khi chu hien ro; speech detection co the nham nhac/hat voi loi thoai; user van can review caption va video final.

## Ghi Chu

- TTS mac dinh dung `edge_tts` voice tieng Viet neural va xuat `*_voice.mp3`. Piper co the xuat `.wav`; gTTS la backup online va silent la fallback cuoi.
- Neu bat nhac nhung khong tim thay file hop le, output van render va warning nam trong `video_XXX_log.json`.
- Neu subtitle burn loi do filter/font/path, renderer fallback sang final video co overlay va voice nhung khong co subtitle.
- Neu mot output loi, batch van tiep tuc render cac output con lai.
