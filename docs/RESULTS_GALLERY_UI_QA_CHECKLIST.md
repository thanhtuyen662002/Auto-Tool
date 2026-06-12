# Results Gallery + Export Pack UI QA Checklist

Prompt 48 scope: `/results`, `/results/:jobId`, `/results/:projectId/:jobId`.

## Automated Checks

- [x] `npm run build` passes for `frontend`.
- [x] `git diff --check` passes.

## Desktop Browser QA

- [x] Results detail page loads existing job outputs without API regressions.
- [x] Summary cards show total, ready, warnings, failed, QA score, and selected/exportable counts.
- [x] Filter tabs, search, sort, grid/compact toggle, and selection mode work.
- [x] Video cards avoid eager video playback and open a preview modal on demand.
- [x] Preview modal plays the selected video and exposes copy path/caption/log actions.
- [x] Final QA panel shows current QA state and keeps Run Final QA available.
- [x] Retry panel appears only when failed/QA-failed outputs exist.
- [x] Export Pack panel computes output indexes for selected/all/QA scopes.
- [x] Technical log drawer shows file paths, warnings, errors, QA issues, and recent job logs.

## Mobile Browser QA

- [x] At 390px width, header actions wrap cleanly.
- [x] Filter/search controls remain usable without horizontal overflow.
- [x] Gallery cards, side panels, preview modal, and log drawer fit the viewport.

## Notes

- Export Pack creation should be tested with a disposable job or confirmed output folder, because it writes local package files.
- Retry should be tested only on a job where creating a new queue item is acceptable.
- Browser QA used job `f44659da-a55c-4570-94c2-ba3ccf3a137c`; export pack creation and retry were intentionally not clicked.
