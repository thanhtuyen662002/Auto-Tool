# Douyin Reup Test Pack

This pack is for real-batch QA of the Douyin Reup flow. Do not commit real videos.

Place local test videos here:

```txt
sample_videos/douyin_reup_test_pack/
```

Recommended minimum set:

```txt
- 3 videos with clear dialogue
- 3 videos with loud background music or quiet dialogue
- 2 videos without clear speech
- 2 videos shorter than 10 seconds
- 2 videos longer than 30 seconds
- 2 landscape or square videos if available
```

Run review-mode QA:

```bash
cd backend
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_review_mode.json
```

Run without Gemini for integration checks:

```bash
cd backend
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_review_mode.json --mock-translation
```

Run auto-render mode:

```bash
cd backend
python -m app.tools.douyin_reup_e2e_test --config ../examples/douyin_reup_test_pack/configs/douyin_reup_auto_render.json --auto-render
```
