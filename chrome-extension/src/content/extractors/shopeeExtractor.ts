import type { ExtractorFieldDebug, ShopeeExtractorDebugReport, ShopeeRawProduct } from "../../shared/types";
import { isShopeeUrl, isSupportedShopeeProductPage } from "../../shared/validators";
import {
  absoluteUrl,
  allTextCandidates,
  cleanText,
  firstDefined,
  metaContent,
  readJsonLdObjects,
  srcFromImage,
  uniqueStrings,
  type JsonObject,
} from "./domUtils";

type FieldCandidate = {
  value?: string;
  method: ExtractorFieldDebug["method"];
  confidence: number;
  warnings?: string[];
};

type PickedField = {
  value?: string;
  debug: ExtractorFieldDebug;
};

const CONFIDENCE_WEIGHTS: Record<string, number> = {
  name: 0.3,
  description: 0.25,
  specs: 0.2,
  brand: 0.1,
  images: 0.1,
  shop: 0.05,
};

export async function extractShopeeProduct(): Promise<ShopeeRawProduct> {
  if (!isShopeeUrl(window.location.href)) {
    throw new Error("Current page is not a Shopee page.");
  }

  const jsonLd = findProductJsonLd();
  const scriptFallback = readScriptStateFallback();
  const textBlocks = allTextCandidates(document).slice(0, 40);
  const ids = extractIdsFromUrl(window.location.href, scriptFallback);
  const extractedAt = new Date().toISOString();

  const nameResult = pickField("name", [
    { value: jsonString(jsonLd, "name"), method: "json_ld", confidence: 0.98 },
    { value: metaContent(["og:title", "twitter:title"]), method: "meta", confidence: 0.9 },
    { value: textFromProductTitle(), method: "dom_selector", confidence: 0.82 },
    { value: scriptFallback.name, method: "script_state", confidence: 0.72 },
    { value: findLikelyProductName(textBlocks), method: "visible_text", confidence: 0.5 },
  ]);
  const descriptionResult = pickField("description", [
    { value: jsonString(jsonLd, "description"), method: "json_ld", confidence: 0.95 },
    { value: metaContent(["og:description", "description", "twitter:description"]), method: "meta", confidence: 0.86 },
    {
      value: textFromSelectorsSafe([
        "[data-testid='pdp-description']",
        ".product-detail",
        ".page-product__detail",
        ".product-description",
      ]),
      method: "dom_selector",
      confidence: 0.76,
    },
    { value: scriptFallback.description, method: "script_state", confidence: 0.7 },
    { value: textByHeading(textBlocks, ["mo ta", "description"]), method: "visible_text", confidence: 0.5 },
  ]);
  const priceResult = pickField("price", [
    { value: offerValue(jsonLd, "price"), method: "json_ld", confidence: 0.95 },
    { value: metaContent(["product:price:amount"]), method: "meta", confidence: 0.84 },
    {
      value: textFromSelectorsSafe(["[data-testid='pdp-price']", ".product-price", ".pdp-product-price"]),
      method: "dom_selector",
      confidence: 0.76,
    },
    { value: scriptFallback.price, method: "script_state", confidence: 0.68 },
    {
      value: findTextByPattern(textBlocks, /(?:\u20ab|VND|d)\s?[\d.,]+|[\d.,]+\s?(?:\u20ab|VND|d)/i),
      method: "visible_text",
      confidence: 0.5,
    },
  ]);
  const specs = extractSpecifications(textBlocks, jsonLd);
  const brandResult = pickField("brand", [
    { value: jsonBrand(jsonLd), method: "json_ld", confidence: 0.95 },
    { value: metaContent(["product:brand", "brand"]), method: "meta", confidence: 0.82 },
    { value: specs["Thuong hieu"] || specs.Brand || specs.brand, method: "dom_selector", confidence: 0.72 },
    { value: scriptFallback.brand, method: "script_state", confidence: 0.65 },
    { value: findBrandFromVisibleText(textBlocks), method: "visible_text", confidence: 0.45 },
  ]);
  const images = extractImages(jsonLd);
  const shopName = textFromSelectorsSafe(["[data-testid='shop-name']", ".shop-page__info-name", "a[href*='/shop/']"]);

  const product: ShopeeRawProduct = {
    source: "shopee",
    url: window.location.href,
    extractedAt,
    productId: ids.productId,
    shopId: ids.shopId,
    name: nameResult.value,
    brand: brandResult.value,
    price: priceResult.value,
    originalPrice: findTextByPattern(textBlocks, /gia goc|original price/i),
    discount: findTextByPattern(textBlocks, /giam\s?gia|discount|-\d+%/i),
    rating: firstDefined(
      aggregateValue(jsonLd, "ratingValue"),
      findTextByPattern(textBlocks, /\b[0-5](?:\.\d)?\s*(?:\/\s*5|sao)?\b/i),
    ),
    soldCount: findTextByPattern(textBlocks, /da ban|sold/i),
    reviewCount: firstDefined(aggregateValue(jsonLd, "reviewCount"), findTextByPattern(textBlocks, /danh gia|reviews?/i)),
    shopName,
    shopLocation: findTextByPattern(textBlocks, /dia chi|location|gui tu/i),
    images,
    videoUrls: extractVideos(),
    categoryBreadcrumbs: extractBreadcrumbs(),
    description: descriptionResult.value,
    specifications: specs,
    variations: extractVariations(textBlocks),
    shippingInfo: findTextByPattern(textBlocks, /van chuyen|shipping|phi ship/i),
    vouchers: extractVouchers(textBlocks),
    rawTextBlocks: textBlocks,
    warnings: [],
  };

  product.warnings = buildWarnings(product, jsonLd);
  const productPage = isSupportedShopeeProductPage(window.location.href, pageSignals(product, jsonLd));
  const pageType: ShopeeExtractorDebugReport["pageType"] = productPage ? "product" : "unknown";
  const debugFields: ExtractorFieldDebug[] = [
    nameResult.debug,
    descriptionResult.debug,
    debugObjectField(
      "specs",
      Object.keys(specs).length > 0,
      Object.keys(specs).length ? `${Object.keys(specs).length} specs` : undefined,
      Object.keys(specs).length > 0 ? "dom_selector" : "fallback",
      Object.keys(specs).length > 0 ? 0.72 : 0,
      Object.keys(specs).length > 0 ? [] : ["Specifications were not found."],
    ),
    brandResult.debug,
    debugObjectField(
      "images",
      images.length > 0,
      images.length ? `${images.length} images` : undefined,
      imageDebugMethod(jsonLd, images),
      images.length > 0 ? 0.78 : 0,
      images.length > 0 ? [] : ["Product images were not found."],
    ),
    debugObjectField(
      "shop",
      Boolean(shopName),
      shopName,
      shopName ? "dom_selector" : "fallback",
      shopName ? 0.72 : 0,
      shopName ? [] : ["Shop name was not found."],
    ),
  ];

  if (!productPage) {
    product.warnings.push(
      "Trang hien tai chua co du dau hieu la trang chi tiet san pham Shopee. Hay kiem tra lai du lieu preview.",
    );
  }
  product.extractorDebug = buildDebugReport(window.location.href, extractedAt, pageType, debugFields, product.warnings);
  if (!productPage) {
    throw new Error("Current Shopee page is not a supported product page.");
  }
  return product;
}

export function parseSpecificationsFromText(text: string): Record<string, string> {
  const specs: Record<string, string> = {};
  const preparedText = text.replace(
    /\s+(?=(?:brand|origin|material|size|pin|battery|android|brightness|do sang|thuong hieu|xuat xu|chat lieu|kich thuoc|he dieu hanh)\b\s*(?:\:|-)?)/gi,
    "\n",
  );
  const lines = preparedText
    .split(/\n|;|\|/)
    .flatMap((line) => line.split(/\s{2,}/))
    .map((line) => cleanText(line))
    .filter((line): line is string => Boolean(line));

  for (const line of lines) {
    const pair = parseSpecPair(line);
    if (pair && !specs[pair.key]) {
      specs[pair.key] = pair.value;
    }

    const normalized = normalizeText(line);
    if (!specs["Pin"]) {
      const battery = line.match(/\b(?:pin|battery)\s*(?:\:|-)?\s*([0-9][0-9.,]*\s*(?:mah|mAh|wh|Whr)?)/i);
      if (battery) {
        specs["Pin"] = cleanText(battery[1]) || battery[1];
      }
    }
    if (!specs["Do phan giai"] && /\b(?:4k|1080p|full hd|hd)\b/i.test(line)) {
      specs["Do phan giai"] = cleanText(line) || line;
    }
    if (!specs["He dieu hanh"]) {
      const android = line.match(/\bandroid\s*([0-9]+(?:\.[0-9]+)*)?/i);
      if (android) {
        specs["He dieu hanh"] = cleanText(android[0]) || "Android";
      }
    }
    if (!specs["Xuat xu"]) {
      const origin = normalized.match(/\b(?:origin|xuat xu)\s*(?:\:|-)?\s*(.+)$/);
      if (origin?.[1]) {
        specs["Xuat xu"] = cleanText(origin[1]) || origin[1];
      }
    }
  }

  return specs;
}

function findProductJsonLd(): JsonObject | undefined {
  return readJsonLdObjects().find((object) => {
    const type = object["@type"];
    return Array.isArray(type) ? type.includes("Product") : type === "Product";
  });
}

function textFromSelectorsSafe(selectors: string[]): string | undefined {
  for (const selector of selectors) {
    const text = cleanText(document.querySelector(selector)?.textContent);
    if (text) {
      return text;
    }
  }
  return undefined;
}

function textFromProductTitle(): string | undefined {
  return textFromSelectorsSafe([
    "h1",
    "[data-testid='pdp-product-title']",
    ".product-briefing h1",
    ".page-product__content h1",
  ]);
}

function extractIdsFromUrl(url: string, fallback: Record<string, string | undefined>): { productId?: string; shopId?: string } {
  const match = url.match(/-i\.(\d+)\.(\d+)/);
  if (match) {
    return { shopId: match[1], productId: match[2] };
  }
  return {
    shopId: fallback.shopId || url.match(/[?&]shopid=(\d+)/)?.[1],
    productId: fallback.productId || url.match(/[?&]itemid=(\d+)/)?.[1],
  };
}

function extractImages(productJsonLd: JsonObject | undefined): string[] {
  const values: Array<string | undefined> = [metaContent(["og:image", "twitter:image"])];
  const image = productJsonLd?.image;
  if (typeof image === "string") {
    values.push(absoluteUrl(image));
  } else if (Array.isArray(image)) {
    values.push(...image.map((item) => (typeof item === "string" ? absoluteUrl(item) : undefined)));
  }
  values.push(
    ...Array.from(document.querySelectorAll<HTMLImageElement>("img"))
      .slice(0, 80)
      .map((img) => srcFromImage(img)),
  );
  return uniqueStrings(values, 20);
}

function extractVideos(): string[] {
  return uniqueStrings(
    Array.from(document.querySelectorAll<HTMLVideoElement>("video")).map((video) =>
      absoluteUrl(video.currentSrc || video.src || video.querySelector("source")?.src),
    ),
    8,
  );
}

function extractBreadcrumbs(): string[] {
  return uniqueStrings(
    Array.from(document.querySelectorAll("nav a, ol a, [aria-label*='breadcrumb' i] a")).map((node) =>
      cleanText(node.textContent),
    ),
    12,
  );
}

function extractSpecifications(textBlocks: string[], productJsonLd: JsonObject | undefined): Record<string, string> {
  const specs: Record<string, string> = {};
  const brand = jsonBrand(productJsonLd);
  if (brand) {
    specs["Thuong hieu"] = brand;
  }

  for (const block of textBlocks) {
    Object.assign(specs, withoutExistingKeys(specs, parseSpecificationsFromText(block)));
    if (Object.keys(specs).length >= 30) {
      break;
    }
  }
  return specs;
}

function parseSpecPair(line: string): { key: string; value: string } | undefined {
  const match = line.match(/^(.{2,50}?)(?:\:|-)\s*(.{1,160})$/) || line.match(/^(brand|origin|material|size|pin)\s+(.{1,160})$/i);
  if (!match) {
    return undefined;
  }

  const rawKey = cleanText(match[1]);
  const rawValue = cleanText(match[2]);
  if (!rawKey || !rawValue) {
    return undefined;
  }

  const normalizedKey = normalizeText(rawKey);
  const mappedKey =
    mapSpecKey(normalizedKey) ||
    (normalizedKey.length <= 40 && !/^(mua ngay|chat|voucher|flash sale|theo doi)/.test(normalizedKey) ? rawKey : undefined);
  if (!mappedKey) {
    return undefined;
  }
  return { key: mappedKey, value: rawValue };
}

function mapSpecKey(normalizedKey: string): string | undefined {
  if (/^(thuong hieu|brand|brand name)$/.test(normalizedKey)) return "Thuong hieu";
  if (/^(xuat xu|origin|made in)$/.test(normalizedKey)) return "Xuat xu";
  if (/^(chat lieu|material)$/.test(normalizedKey)) return "Chat lieu";
  if (/^(kich thuoc|size|dimensions?)$/.test(normalizedKey)) return "Kich thuoc";
  if (/^(pin|battery)$/.test(normalizedKey)) return "Pin";
  if (/^(he dieu hanh|operating system|os)$/.test(normalizedKey)) return "He dieu hanh";
  if (/^(do phan giai|resolution)$/.test(normalizedKey)) return "Do phan giai";
  return undefined;
}

function withoutExistingKeys(current: Record<string, string>, incoming: Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(incoming)) {
    if (!current[key] && Object.keys(current).length + Object.keys(result).length < 30) {
      result[key] = value;
    }
  }
  return result;
}

function extractVariations(textBlocks: string[]): ShopeeRawProduct["variations"] {
  const candidates = textBlocks.filter((text) => /phan loai|variation|mau sac|kich co|size|color/i.test(text));
  const variations: NonNullable<ShopeeRawProduct["variations"]> = [];
  for (const text of candidates.slice(0, 4)) {
    const [namePart, optionsPart] = text.split(/:|-/);
    const name = cleanText(namePart);
    if (!name || !optionsPart) {
      continue;
    }
    const options = uniqueStrings(optionsPart.split(/,|\/|\|/), 12);
    if (options.length > 0) {
      variations.push({ name, options });
    }
  }
  return variations.length ? variations : undefined;
}

function extractVouchers(textBlocks: string[]): string[] {
  return uniqueStrings(textBlocks.filter((text) => /voucher|ma giam gia|uu dai|discount/i.test(text)), 8);
}

function textByHeading(textBlocks: string[], headings: string[]): string | undefined {
  return textBlocks.find((text) => headings.some((heading) => normalizeText(text).includes(heading)));
}

function findTextByPattern(textBlocks: string[], pattern: RegExp): string | undefined {
  return textBlocks.find((text) => pattern.test(text));
}

function findLikelyProductName(textBlocks: string[]): string | undefined {
  return textBlocks.find((text) => {
    const normalized = normalizeText(text);
    return (
      text.length >= 8 &&
      text.length <= 180 &&
      !/^(shop|voucher|flash sale|gio hang|dang nhap|tim kiem|category|danh muc)/.test(normalized) &&
      !/mua ngay|them vao gio hang|van chuyen/.test(normalized)
    );
  });
}

function findBrandFromVisibleText(textBlocks: string[]): string | undefined {
  for (const text of textBlocks) {
    const spec = parseSpecificationsFromText(text);
    if (spec["Thuong hieu"]) {
      return spec["Thuong hieu"];
    }
  }
  return undefined;
}

function jsonString(object: JsonObject | undefined, key: string): string | undefined {
  const value = object?.[key];
  return typeof value === "string" ? cleanText(value) : undefined;
}

function jsonBrand(object: JsonObject | undefined): string | undefined {
  const brand = object?.brand;
  if (typeof brand === "string") {
    return cleanText(brand);
  }
  if (brand && typeof brand === "object" && !Array.isArray(brand)) {
    const name = (brand as JsonObject).name;
    return typeof name === "string" ? cleanText(name) : undefined;
  }
  return undefined;
}

function offerValue(object: JsonObject | undefined, key: string): string | undefined {
  const offers = object?.offers;
  if (!offers || typeof offers !== "object" || Array.isArray(offers)) {
    return undefined;
  }
  const value = (offers as JsonObject)[key];
  return typeof value === "string" || typeof value === "number" ? cleanText(String(value)) : undefined;
}

function aggregateValue(object: JsonObject | undefined, key: string): string | undefined {
  const aggregateRating = object?.aggregateRating;
  if (!aggregateRating || typeof aggregateRating !== "object" || Array.isArray(aggregateRating)) {
    return undefined;
  }
  const value = (aggregateRating as JsonObject)[key];
  return typeof value === "string" || typeof value === "number" ? cleanText(String(value)) : undefined;
}

function readScriptStateFallback(): Record<string, string | undefined> {
  const joined = Array.from(document.scripts)
    .map((script) => script.textContent || "")
    .join("\n")
    .slice(0, 1_500_000);
  return {
    productId: joined.match(/"itemid"\s*:\s*(\d+)/)?.[1],
    shopId: joined.match(/"shopid"\s*:\s*(\d+)/)?.[1],
    name: cleanScriptString(joined.match(/"name"\s*:\s*"([^"]{5,240})"/)?.[1]),
    brand: cleanScriptString(joined.match(/"brand"\s*:\s*"([^"]{2,120})"/)?.[1]),
    description: cleanScriptString(joined.match(/"description"\s*:\s*"([^"]{10,800})"/)?.[1]),
    price: joined.match(/"price"\s*:\s*(\d+)/)?.[1],
  };
}

function cleanScriptString(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return cleanText(value.replace(/\\"/g, '"').replace(/\\n/g, "\n"));
}

function pickField(field: string, candidates: FieldCandidate[]): PickedField {
  const found = candidates.find((candidate) => cleanText(candidate.value));
  if (!found) {
    return {
      value: undefined,
      debug: debugObjectField(field, false, undefined, "fallback", 0, [`${field} was not found.`]),
    };
  }
  const value = cleanText(found.value);
  const warnings = found.warnings || [];
  if (found.method === "visible_text" || found.method === "fallback") {
    warnings.push(`${field} used a low-confidence fallback.`);
  }
  return {
    value,
    debug: debugObjectField(field, true, value, found.method, found.confidence, warnings),
  };
}

function debugObjectField(
  field: string,
  valueFound: boolean,
  valuePreview: string | undefined,
  method: ExtractorFieldDebug["method"],
  confidence: number,
  warnings: string[],
): ExtractorFieldDebug {
  return {
    field,
    valueFound,
    valuePreview: valuePreview ? truncate(valuePreview, 120) : undefined,
    method,
    confidence: clamp01(confidence),
    warnings: uniqueStrings(warnings, 6),
  };
}

function buildDebugReport(
  url: string,
  extractedAt: string,
  pageType: ShopeeExtractorDebugReport["pageType"],
  fields: ExtractorFieldDebug[],
  warnings: string[],
): ShopeeExtractorDebugReport {
  return {
    url,
    extractedAt,
    pageType,
    fields,
    overallConfidence: weightedConfidence(fields),
    warnings: uniqueStrings(warnings, 12),
  };
}

function weightedConfidence(fields: ExtractorFieldDebug[]): number {
  const byName = new Map(fields.map((field) => [field.field, field]));
  let total = 0;
  for (const [field, weight] of Object.entries(CONFIDENCE_WEIGHTS)) {
    const debug = byName.get(field);
    total += weight * (debug?.valueFound ? debug.confidence : 0);
  }
  return Number(clamp01(total).toFixed(3));
}

function imageDebugMethod(
  productJsonLd: JsonObject | undefined,
  images: string[],
): ExtractorFieldDebug["method"] {
  if (!images.length) {
    return "fallback";
  }
  const image = productJsonLd?.image;
  if (image) {
    return "json_ld";
  }
  if (metaContent(["og:image", "twitter:image"])) {
    return "meta";
  }
  return "dom_selector";
}

function buildWarnings(product: ShopeeRawProduct, productJsonLd: JsonObject | undefined): string[] {
  const warnings: string[] = [];
  if (!product.name) {
    warnings.push("Khong extract duoc ten san pham.");
  }
  if (!product.brand) {
    warnings.push("Khong tim thay thuong hieu.");
  }
  if (!product.description) {
    warnings.push("Khong tim thay mo ta san pham, da dung fallback text neu co.");
  }
  if (!product.specifications || Object.keys(product.specifications).length === 0) {
    warnings.push("Khong tim thay thong so san pham.");
  }
  if (!productJsonLd) {
    warnings.push("Khong tim thay JSON-LD Product, mot so field duoc lay bang DOM/text fallback.");
  }
  return uniqueStrings(warnings, 10);
}

function pageSignals(product: ShopeeRawProduct, productJsonLd: JsonObject | undefined) {
  return {
    hasProductTitle: Boolean(product.name),
    hasProductSchema: Boolean(productJsonLd),
    hasPrice: Boolean(product.price),
  };
}

function truncate(value: string, maxLength: number): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength - 3).trim()}...`;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\u0111/g, "d")
    .replace(/\u0110/g, "D")
    .toLocaleLowerCase();
}
