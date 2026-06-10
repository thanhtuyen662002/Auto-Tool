# Expected Outputs

A successful Douyin Reup v1.0 RC run should create a timestamped output folder under `examples/outputs/douyin_reup_v1_rc/`.

Expected files:

- `job_log.json`
- `douyin_reup_summary.json`
- `final_qa_summary.json` when render is enabled
- `export_manifest.json` when Export Pack is enabled
- Per-video folders such as `video_001/`

Each video folder should contain the artifacts that apply to that video:

- `video_001_log.json`
- Source subtitle if detected or generated
- Translated subtitle
- Corrected subtitle when approved through review
- ASS subtitle when rendered
- OCR debug JSON when OCR is used
- Final QA report when rendered

Safe Review mode is expected to stop at `needs_review` and create review documents. Fast Auto and Music Recut are expected to render directly when dependencies and input videos are valid.
