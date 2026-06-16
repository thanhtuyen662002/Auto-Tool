# Auto Tool Douyin Reup v1.0.0-rc1

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
