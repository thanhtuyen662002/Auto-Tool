import { describe, expect, it } from "vitest";
import { normalizeShopeeToAutoToolPayload } from "../src/content/extractors/normalizeShopeeProduct";
import type { ShopeeRawProduct } from "../src/shared/types";
import { validatePayload } from "../src/shared/validators";

function rawProduct(overrides: Partial<ShopeeRawProduct> = {}): ShopeeRawProduct {
  return {
    source: "shopee",
    url: "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
    extractedAt: "2026-06-08T00:00:00.000Z",
    name: "May chieu KAW XMAX10",
    brand: "KAW",
    price: "1.990.000d",
    description: "Ho tro 4K\nHo tro 4K\nAndroid 9.0",
    specifications: {
      "Thuong hieu": "KAW",
      "Do sang": "10000 Lumens",
    },
    variations: [{ name: "Mau sac", options: ["Den", "Trang"] }],
    shopName: "KAW Official",
    images: ["https://down-vn.img.susercontent.com/file/test.jpg"],
    warnings: [],
    ...overrides,
  };
}

describe("normalizeShopeeToAutoToolPayload", () => {
  it("normalizes raw Shopee data into Auto Tool payload", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct());

    expect(payload.input_type).toBe("shopee_extension");
    expect(payload.source_name).toBe("shopee");
    expect(payload.source_url).toContain("shopee.vn");
    expect(payload.structured_data.name).toBe("May chieu KAW XMAX10");
    expect(payload.structured_data.brand).toBe("KAW");
    expect(payload.structured_data.price).toBe("1.990.000d");
    expect(payload.structured_data.images).toHaveLength(1);
  });

  it("creates a valid payload when brand is missing", () => {
    const payload = normalizeShopeeToAutoToolPayload(
      rawProduct({ brand: undefined, specifications: { "Do sang": "10000 Lumens" }, warnings: ["Khong tim thay thuong hieu."] }),
    );

    expect(payload.structured_data.brand).toBeUndefined();
    expect(validatePayload(payload)).toEqual([]);
    expect(payload.structured_data.shopee?.warnings).toContain("Khong tim thay thuong hieu.");
  });

  it("converts specs object into specs array", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct());

    expect(payload.structured_data.specs).toContainEqual({ name: "Do sang", value: "10000 Lumens" });
  });

  it("removes duplicate features", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct());

    expect(payload.structured_data.features.filter((feature) => feature === "Ho tro 4K")).toHaveLength(1);
  });

  it("builds raw_text with product, specs, shop, and URL", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct());

    expect(payload.raw_text).toContain("Ten san pham: May chieu KAW XMAX10");
    expect(payload.raw_text).toContain("- Do sang: 10000 Lumens");
    expect(payload.raw_text).toContain("Shop: KAW Official");
    expect(payload.raw_text).toContain("URL: https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456");
  });

  it("falls back to name and features when description is missing", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct({ description: undefined }));

    expect(payload.structured_data.description).toContain("May chieu KAW XMAX10");
    expect(payload.structured_data.description.length).toBeGreaterThan(20);
  });
});
