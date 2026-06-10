# Auto Tool Douyin Reup v1.0.0-rc1

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
