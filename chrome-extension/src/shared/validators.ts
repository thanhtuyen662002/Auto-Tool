import type { AutoToolProductPayload } from "./types";

export function isShopeeUrl(rawUrl: string | undefined): boolean {
  if (!rawUrl) {
    return false;
  }
  try {
    const url = new URL(rawUrl);
    return url.protocol === "https:" && (url.hostname === "shopee.vn" || url.hostname.endsWith(".shopee.vn"));
  } catch {
    return false;
  }
}

export function isSupportedShopeeProductPage(
  rawUrl: string | undefined,
  signals: { hasProductTitle?: boolean; hasProductSchema?: boolean; hasPrice?: boolean } = {},
): boolean {
  if (!isShopeeUrl(rawUrl)) {
    return false;
  }
  if (!rawUrl) {
    return false;
  }
  return rawUrl.includes("-i.") || Boolean(signals.hasProductTitle || signals.hasProductSchema || signals.hasPrice);
}

export function normalizeBaseUrl(value: string): string {
  const cleaned = value.trim().replace(/\/+$/, "");
  return cleaned || "http://localhost:8000";
}

export function validatePayload(payload: AutoToolProductPayload | undefined): string[] {
  return validateAutoToolPayload(payload).errors;
}

export function validateAutoToolPayload(
  payload: AutoToolProductPayload | undefined,
): { valid: boolean; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];
  if (!payload) {
    return { valid: false, errors: ["Payload is empty."], warnings };
  }
  if (payload.input_type !== "shopee_extension") {
    errors.push("Payload input_type must be shopee_extension.");
  }
  if (payload.source_name !== "shopee") {
    errors.push("Payload source_name must be shopee.");
  }
  if (!isShopeeUrl(payload.source_url)) {
    errors.push("Payload source_url must be a Shopee product URL.");
  }
  if (!payload.structured_data.name.trim()) {
    errors.push("Product name is required.");
  }
  if (!payload.structured_data.description.trim() && payload.structured_data.features.length === 0) {
    errors.push("Product description or at least one feature is required.");
  }
  if (!payload.raw_text.trim()) {
    errors.push("raw_text is required.");
  }

  if (!payload.structured_data.brand?.trim()) {
    warnings.push("Brand is missing.");
  }
  if (payload.structured_data.specs.length === 0) {
    warnings.push("Specifications are missing.");
  }
  if (!payload.structured_data.images || payload.structured_data.images.length === 0) {
    warnings.push("Product images are missing.");
  }
  if (payload.structured_data.description.trim() && payload.structured_data.description.trim().length < 40) {
    warnings.push("Description is short.");
  }
  if (payload.structured_data.features.length < 2) {
    warnings.push("Fewer than 2 features were extracted.");
  }

  return { valid: errors.length === 0, errors, warnings };
}
