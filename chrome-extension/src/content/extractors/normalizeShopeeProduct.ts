import type { AutoToolProductPayload, ShopeeRawProduct } from "../../shared/types";

export function normalizeShopeeToAutoToolPayload(raw: ShopeeRawProduct): AutoToolProductPayload {
  const specs = normalizeSpecs(raw.specifications);
  const brand = clean(raw.brand) || brandFromSpecs(raw.specifications);
  const features = extractFeatures(raw);
  const description = buildDescription(raw.name, raw.description, features);
  const structuredData: AutoToolProductPayload["structured_data"] = {
    name: clean(raw.name) || "",
    brand,
    description,
    features,
    specs,
    cta: raw.price ? "Xem chi tiet san pham tren Shopee" : "Xem chi tiet san pham ngay",
    price: clean(raw.price),
    images: raw.images?.slice(0, 12),
    variations: raw.variations?.slice(0, 12),
    shop: {
      name: clean(raw.shopName),
      location: clean(raw.shopLocation),
    },
    shopee: raw,
  };

  return {
    input_type: "shopee_extension",
    source_name: "shopee",
    source_url: raw.url,
    save_to_inbox: true,
    raw_text: buildRawTextFromStructuredData(structuredData, raw.url),
    structured_data: structuredData,
    extractor_debug: raw.extractorDebug,
  };
}

export function buildRawTextFromStructuredData(
  data: AutoToolProductPayload["structured_data"],
  sourceUrl: string,
): string {
  const lines = [
    `Ten san pham: ${data.name}`,
    data.brand ? `Thuong hieu: ${data.brand}` : undefined,
    data.price ? `Gia: ${data.price}` : undefined,
    data.description ? `Mo ta: ${data.description}` : undefined,
    data.features.length ? "Diem noi bat:" : undefined,
    ...data.features.map((feature) => `- ${feature}`),
    data.specs.length ? "Thong so:" : undefined,
    ...data.specs.map((spec) => `- ${spec.name}: ${spec.value}`),
    data.variations?.length ? "Phan loai:" : undefined,
    ...(data.variations || []).map((variation) => `- ${variation.name}: ${variation.options.join(", ")}`),
    data.shop?.name ? `Shop: ${data.shop.name}` : undefined,
    data.shop?.location ? `Dia chi shop: ${data.shop.location}` : undefined,
    `URL: ${sourceUrl}`,
  ];
  return lines.filter(Boolean).join("\n");
}

export function extractFeatures(raw: ShopeeRawProduct): string[] {
  return buildFeatures(raw, normalizeSpecs(raw.specifications));
}

function buildFeatures(raw: ShopeeRawProduct, specs: Array<{ name: string; value: string }>): string[] {
  const values: string[] = [];
  values.push(...descriptionBullets(raw.description));
  values.push(...specs.slice(0, 6).map((spec) => `${spec.name}: ${spec.value}`));
  if (raw.price) {
    values.push(`Gia hien thi: ${raw.price}`);
  }
  if (raw.discount) {
    values.push(`Uu dai: ${raw.discount}`);
  }
  if (raw.variations?.length) {
    values.push(...raw.variations.map((variation) => `${variation.name}: ${variation.options.slice(0, 4).join(", ")}`));
  }
  if (raw.shopName) {
    values.push(`Shop: ${raw.shopName}`);
  }
  return uniqueLimited(values.filter((value) => !isSpamFeature(value)), 8, 90);
}

function buildDescription(name: string | undefined, description: string | undefined, features: string[]): string {
  const cleanedName = clean(name);
  const cleanedDescription = clean(description);
  if (cleanedDescription && cleanedName && !cleanedDescription.includes(cleanedName)) {
    return truncate(`${cleanedName}. ${cleanedDescription}`, 700);
  }
  if (cleanedDescription) {
    return truncate(cleanedDescription, 700);
  }
  return truncate([cleanedName, ...features.slice(0, 3)].filter(Boolean).join(". "), 700);
}

function normalizeSpecs(specifications: ShopeeRawProduct["specifications"]): Array<{ name: string; value: string }> {
  if (!specifications) {
    return [];
  }
  return Object.entries(specifications)
    .map(([name, value]) => ({ name: clean(name) || "", value: clean(value) || "" }))
    .filter((spec) => spec.name && spec.value)
    .slice(0, 15);
}

function brandFromSpecs(specifications: ShopeeRawProduct["specifications"]): string | undefined {
  if (!specifications) {
    return undefined;
  }
  for (const [key, value] of Object.entries(specifications)) {
    const normalizedKey = normalizeText(key);
    if (normalizedKey === "brand" || normalizedKey === "brand name" || normalizedKey === "thuong hieu") {
      return clean(value);
    }
  }
  return undefined;
}

function descriptionBullets(description: string | undefined): string[] {
  if (!description) {
    return [];
  }
  return description
    .split(/\n|;|\|/)
    .map((line) => line.replace(/^[-*+.]\s*/, ""))
    .map(clean)
    .filter((line): line is string => Boolean(line && line.length >= 8));
}

function uniqueLimited(values: Array<string | undefined>, limit: number, maxLength: number): string[] {
  const seen = new Set<string>();
  const results: string[] = [];
  for (const value of values) {
    const cleaned = clean(value);
    if (!cleaned) {
      continue;
    }
    const shortened = truncate(cleaned, maxLength);
    const key = normalizeText(shortened);
    if (seen.has(key)) {
      continue;
    }
    results.push(shortened);
    seen.add(key);
    if (results.length >= limit) {
      break;
    }
  }
  return results;
}

function isSpamFeature(value: string | undefined): boolean {
  const text = normalizeText(value || "");
  if (!text) {
    return true;
  }
  const spamPatterns = [
    /theo doi shop/,
    /follow shop/,
    /nhan voucher/,
    /voucher/,
    /flash sale/,
    /mien phi van chuyen/,
    /freeship/,
    /chat ngay/,
    /dat hang/,
    /mua ngay/,
    /cam on quy khach/,
    /bao hanh doi tra vui long/i,
  ];
  return spamPatterns.some((pattern) => pattern.test(text));
}

function clean(value: string | undefined): string | undefined {
  const cleaned = value?.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  return cleaned || undefined;
}

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 3).trim()}...`;
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLocaleLowerCase();
}
