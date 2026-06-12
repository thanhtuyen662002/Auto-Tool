# Auto Tool Studio Glass UI QA Checklist

## Navigation and layout

- [x] Dashboard has three clear workflow CTAs.
- [x] Sidebar contains only Dashboard, Douyin Reup, Silent Mode, Subtitle Review, Results, and Settings.
- [x] Sidebar collapses below desktop width.
- [x] Right Insight Panel moves below the main form before the 1280px breakpoint.
- [x] Glass surfaces keep readable contrast and use a maximum 8px radius.

## Workflows

- [x] Douyin Reup Simple Mode shows source, output, preset, optional music, and the start action.
- [x] Silent Mode exposes preset, industry, tone, and optional music.
- [x] Silent product context is collapsed by default.
- [x] Advanced settings are hidden by default.
- [x] Preset cards explain review, OCR, and Silent behavior without showing raw configuration.
- [x] Right Insight Panel summarizes the selected workflow.
- [x] Job progress hides technical logs until requested.

## Review and results

- [x] Subtitle Review uses readable document and subtitle-line cards.
- [x] Clicking a subtitle line seeks the video to its start time.
- [x] Quality filters, next flagged line, rewrite, approve, and render actions remain available.
- [x] Silent Plan Preview shows representative frames, visual tags, captions, and tag editing.
- [x] Rendered outputs use a responsive gallery with filters.
- [x] Failed output cards show a short reason and keep the technical log optional.
- [x] Final QA has a compact summary rather than raw JSON.
- [x] Export Pack content and output path actions are visible.

## States and accessibility

- [x] Empty states provide a short explanation and relevant CTA.
- [x] API errors are shortened and do not expose a raw traceback in the primary UI.
- [x] Loading states use skeleton surfaces.
- [x] Focus rings are visible on form controls and main buttons.
- [x] Subtitle textareas use a near-solid editor background.
- [x] Primary controls remain usable by keyboard.

## Verification

- [x] `npm run build` completes without TypeScript errors.
- [x] Dashboard checked at 1440x900 with no horizontal overflow.
- [x] Douyin Reup checked at 1440x900; Simple and Advanced modes expose the expected fields.
- [x] Silent Mode checked at 1440x900; industry, tone, presets, and collapsed context are present.
- [x] Subtitle Review checked at 1440x900; selecting a line seeks the video and highlights the card.
- [x] Dashboard, Silent Mode, Subtitle Review, and Results checked at 390x844 with no page overflow.
- [x] Backend Connected status verified against `http://127.0.0.1:8000/api/health`.
