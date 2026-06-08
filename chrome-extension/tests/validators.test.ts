import { describe, expect, it } from "vitest";
import { isShopeeUrl, isSupportedShopeeProductPage, normalizeBaseUrl, validatePayload } from "../src/shared/validators";
import type { AutoToolProductPayload } from "../src/shared/types";

describe("validators", () => {
  it("rejects non-Shopee URLs", () => {
    expect(isShopeeUrl("https://example.com/product")).toBe(false);
    expect(isSupportedShopeeProductPage("https://example.com/product")).toBe(false);
  });

  it("accepts Shopee product URL patterns and page signals", () => {
    expect(isSupportedShopeeProductPage("https://shopee.vn/test-i.1.2")).toBe(true);
    expect(isSupportedShopeeProductPage("https://shopee.vn/test", { hasProductTitle: true })).toBe(true);
  });

  it("normalizes API base URL", () => {
    expect(normalizeBaseUrl(" http://localhost:8000/// ")).toBe("http://localhost:8000");
  });

  it("validates payload required fields", () => {
    const payload: AutoToolProductPayload = {
      input_type: "shopee_extension",
      source_name: "shopee",
      source_url: "https://shopee.vn/test-i.1.2",
      save_to_inbox: true,
      raw_text: "Ten san pham: Test",
      structured_data: {
        name: "Test",
        description: "Mo ta san pham",
        features: ["Feature"],
        specs: [],
        cta: "Xem ngay",
      },
    };

    expect(validatePayload(payload)).toEqual([]);
  });
});
