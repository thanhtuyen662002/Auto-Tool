# Douyin Reup v1.0 RC Test Pack

This folder contains release-candidate configs and QA templates for **Auto Tool Douyin Reup v1.0.0-rc1**.

No real videos are committed to the repo. Put local test videos here:

```txt
sample_videos/douyin_reup_v1_rc/
```

Recommended first run:

```bash
cd backend
python -m app.tools.douyin_reup_v1_rc_test --config ../examples/douyin_reup_v1_rc/configs/v1_safe_review.json --mock-translation
```

For dependency-light validation:

```bash
cd backend
python -m app.tools.douyin_reup_v1_rc_test --config ../examples/douyin_reup_v1_rc/configs/v1_safe_review.json --mock-asr --mock-ocr --mock-translation --review-mode
```

Minimum RC dataset:

- 3 videos with sidecar SRT
- 3 videos with clear Chinese speech
- 3 videos with loud music / low speech
- 3 videos with visible Chinese hard-sub text
- 2 videos without clear speech
- 2 videos shorter than 8 seconds
- 2 videos longer than 30 seconds
- 2 horizontal or square videos
- 1 video without audio
- 1 bad/corrupt video if available

The goal is to exercise:

- SRT source detection
- ASR
- OCR
- Translation
- Subtitle Review
- Rewrite
- Render
- Final QA
- Export Pack
- Retry

Do not use this tool for videos, music, or assets that you do not have permission to edit, translate, or re-render.
