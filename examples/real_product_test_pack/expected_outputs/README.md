# Expected Outputs

Preview mode should create at least:

```txt
preview_001.mp4
preview_001_visual.mp4
preview_001_script.json
preview_001_sub.srt
preview_001_sub.ass
preview_001_voice.*
preview_001_timeline.json
preview_001_log.json
segment_scoring_report.json
crop_safety_report.json
script_variants.json
project_summary.json
content_items.json
content_plan.md
```

Full mode should create 3 output sets:

```txt
video_001.mp4
video_001_script.json
video_001_sub.srt
video_001_sub.ass
video_001_voice.*
video_001_timeline.json
video_001_log.json
...
video_003.*
segment_scoring_report.json
crop_safety_report.json
output_quality_review.json
content_items.json
content_export.json
content_export.csv
content_export.txt
content_plan.md
project_summary.json
```

Each timeline clip should keep source media review metadata when available:

```json
{
  "user_review_status": "favorite",
  "source_media_review_status": "good"
}
```
