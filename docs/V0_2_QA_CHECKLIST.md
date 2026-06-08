# Auto Tool v0.2 QA Checklist

Use this checklist for the v0.2 release-candidate manual QA pass.

## Product Import

- [ ] Paste product text parses name correctly
- [ ] Brand is extracted if present
- [ ] Features are extracted
- [ ] Specs are extracted
- [ ] Industry preset is suggested
- [ ] Risky claims are warned

## Source Media

- [ ] Videos are scanned
- [ ] Bad videos can be excluded
- [ ] Segments are scored
- [ ] Favorite segment is prioritized
- [ ] Excluded segment is not used

## Render Preview

- [ ] Preview renders successfully
- [ ] TTS works or fallback works
- [ ] Subtitle is readable
- [ ] Overlay style is applied
- [ ] Crop safety does not cut important content badly

## Full Batch

- [ ] Output count is correct
- [ ] Each video has unique script
- [ ] Each video has log
- [ ] Each video has timeline JSON
- [ ] Each video has subtitle SRT/ASS
- [ ] Each video has voice file
- [ ] Project summary exists

## Review + Rerender

- [ ] Quality review opens
- [ ] Bad output can be marked
- [ ] Rerender selected works
- [ ] Old output is not deleted

## Captions

- [ ] Caption items are created
- [ ] Caption can be edited
- [ ] Caption + hashtags can be copied
- [ ] CSV export works
- [ ] Markdown plan export works

## Release Decision

- [ ] No blocker bugs remain
- [ ] Known limitations are documented
- [ ] Smoke test JSON result is attached to QA notes
- [ ] Performance baseline is recorded
