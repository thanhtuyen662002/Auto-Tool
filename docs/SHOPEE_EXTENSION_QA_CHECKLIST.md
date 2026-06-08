# Shopee Extension E2E QA Checklist

Use this checklist for the hardened Shopee Extension flow:

```txt
Shopee product page
-> Chrome Extension extract
-> Normalize payload
-> Send to Auto Tool
-> Save Product Draft
-> Create Project from Draft
-> Render Preview
```

## Setup

- [ ] Backend starts at `http://localhost:8000`.
- [ ] Frontend starts at `http://localhost:5173`.
- [ ] `GET http://localhost:8000/api/health` returns `status: ok`.
- [ ] `chrome-extension/npm test` passes.
- [ ] `chrome-extension/npm run build` passes.
- [ ] Extension is loaded unpacked from `chrome-extension/dist`.

## Extension Extract

- [ ] Open a real Shopee product detail page.
- [ ] Popup state shows `Ready`.
- [ ] Click `Extract Product Info`.
- [ ] Popup state changes to `Extracted`.
- [ ] Preview shows product name, description, features, specs, source URL, and shop when available.
- [ ] Extractor confidence is visible.
- [ ] Missing fields are visible.
- [ ] Extractor warnings are visible.
- [ ] If product name is missing, preview is still shown but `Send to Auto Tool` is disabled.
- [ ] Non-product Shopee pages are rejected with a friendly message.

## Payload Validation

- [ ] Payload has `input_type: shopee_extension`.
- [ ] Payload has `source_name: shopee`.
- [ ] Payload has `source_url`.
- [ ] Payload has `save_to_inbox: true`.
- [ ] Payload has top-level `extractor_debug`.
- [ ] `raw_text` includes the Shopee URL.
- [ ] Missing name is an error.
- [ ] Missing description and missing features together are an error.
- [ ] Missing brand/specs/images, short description, and fewer than 2 features are warnings.

## Send To Auto Tool

- [ ] With backend stopped, Send shows a friendly backend-not-running message.
- [ ] With backend running, Send succeeds.
- [ ] Popup state changes to `Sent`.
- [ ] Response includes `draft`.
- [ ] Response includes `import_inbox_url`.
- [ ] `Open Import Inbox` opens `/import-inbox`.
- [ ] `Open Draft` opens `/import-inbox?draft=<draft_id>`.

## Import Inbox

- [ ] New draft appears in Import Inbox.
- [ ] Draft detail shows normalized product fields.
- [ ] Draft detail shows `Extraction Quality`.
- [ ] Extraction Quality shows overall confidence.
- [ ] Extraction Quality shows field methods and confidence.
- [ ] Low confidence report shows a review warning.
- [ ] Raw data includes `extractor_debug`.
- [ ] Draft can be edited and saved.
- [ ] Draft can be archived and deleted.

## Create Project And Render Preview

- [ ] Click `Create Project from Draft`.
- [ ] Fill valid source folder and output folder.
- [ ] Project is created successfully.
- [ ] Project product info matches the draft.
- [ ] Open render settings/result flow.
- [ ] Render preview starts.
- [ ] Preview job completes or returns a clear actionable error.
- [ ] Generated preview uses product name, description, CTA, and features from the draft.

## Regression Notes

- [ ] The extension does not call Shopee APIs.
- [ ] The extension does not read cookies or auth tokens.
- [ ] The extension does not bulk crawl products.
- [ ] Product Drafts remain local in SQLite.
