# Auto Tool Shopee Extractor

Chrome Extension Manifest V3 for extracting visible product information from the current Shopee product page and sending it to the local Auto Tool API.

## Dev Install

1. Run `npm install`
2. Run `npm run build`
3. Open `chrome://extensions`
4. Enable Developer Mode
5. Click Load unpacked
6. Select `chrome-extension/dist`

## Usage

1. Start Auto Tool backend at `http://localhost:8000`
2. Open a Shopee product detail page
3. Click the Auto Tool Shopee Extractor extension
4. Click Extract Product Info
5. Review and edit Name, Brand, Description, or CTA if needed
6. Click Send to Auto Tool
7. The product is saved in Auto Tool Import Inbox
8. Click Open Import Inbox or open `http://localhost:5173/import-inbox`

The popup shows extractor state (`Ready`, `Extracted`, `Sent`), field-level confidence, missing fields, and warnings before Send. If the product name is missing, the preview remains visible but Send is disabled until the user fixes the name.

The extension includes image URLs that are visible or embedded on the current product page in:

- `structured_data.images`
- `structured_data.shopee.images`

Auto Tool does not download those images immediately. In Import Inbox, the user chooses which Product Assets to import/download and which role each image should have.

The popup lets you configure both:

- Auto Tool API URL, default `http://localhost:8000`
- Auto Tool Frontend URL, default `http://localhost:5173`

## Limits

This extension only reads product data already visible or embedded in the current Shopee product page.

It does not crawl products in bulk, bypass anti-bot systems, read cookies, read account data, automate login, automate purchases, post reviews, post videos, or send data to third-party servers.

Data is sent only to the configured local Auto Tool API when the user clicks Send to Auto Tool. The extension can store the latest preview in `chrome.storage.local`; use Clear Saved Data in the popup to remove it.

Auto Tool stores received Product Drafts locally in its SQLite database. Drafts may contain product description, price, Shopee URL, shop info, and validation warnings. Users can delete drafts from Import Inbox at any time.

Auto Tool only saves product images locally after the user explicitly selects and imports them. Users are responsible for ensuring they have the right to use downloaded product images for their intended purpose.

Users should review extracted data before rendering advertising videos. The extension does not independently verify product claims.

## QA

Run automated checks:

```bash
npm test
npm run build
```

Manual E2E checklist:

```txt
../docs/SHOPEE_EXTENSION_QA_CHECKLIST.md
```
