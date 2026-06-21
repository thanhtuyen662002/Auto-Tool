# Auto Tool Douyin Reup v1.0.0-rc1

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
