import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { extractFeatures, normalizeShopeeToAutoToolPayload } from "../src/content/extractors/normalizeShopeeProduct";
import { extractShopeeProduct, parseSpecificationsFromText } from "../src/content/extractors/shopeeExtractor";
import type { ShopeeRawProduct } from "../src/shared/types";

const PRODUCT_URL = "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Shopee extractor", () => {
  it("extracts a basic Shopee product with debug confidence", async () => {
    loadFixture("shopee_product_basic.html", PRODUCT_URL);

    const product = await extractShopeeProduct();

    expect(product.name).toBe("May chieu KAW XMAX10");
    expect(product.brand).toBe("KAW");
    expect(product.images).toContain("https://down-vn.img.susercontent.com/file/basic.jpg");
    expect(product.specifications?.["Do sang"]).toBe("10000 Lumens");
    expect(product.extractorDebug?.pageType).toBe("product");
    expect(product.extractorDebug?.overallConfidence).toBeGreaterThan(0.7);
  });

  it("filters Shopee decorative and unrelated images", async () => {
    loadFixture("shopee_product_basic.html", PRODUCT_URL);

    const product = await extractShopeeProduct();
    const images = product.images ?? [];

    expect(images).toEqual(["https://down-vn.img.susercontent.com/file/basic.jpg"]);
    expect(images.some((image) => image.includes("deo.shopeemobile.com"))).toBe(false);
    expect(images.some((image) => image.includes("shoprating"))).toBe(false);
    expect(images.some((image) => image === PRODUCT_URL)).toBe(false);
  });

  it("adds a warning when brand is missing", async () => {
    loadFixture("shopee_product_missing_brand.html", "https://shopee.vn/Den-LED-cam-ung-i.321.654");

    const product = await extractShopeeProduct();
    const brandField = product.extractorDebug?.fields.find((field) => field.field === "brand");

    expect(product.brand).toBeUndefined();
    expect(product.warnings).toContain("Khong tim thay thuong hieu.");
    expect(brandField?.valueFound).toBe(false);
  });

  it("extracts shop name from current Shopee visible shop block", async () => {
    loadFixture("shopee_product_shop_visible_text.html", "https://shopee.vn/product/40180096/7544569713");

    const product = await extractShopeeProduct();
    const shopField = product.extractorDebug?.fields.find((field) => field.field === "shop");

    expect(product.shopName).toBe("Baby Gaming");
    expect(shopField?.valueFound).toBe(true);
    expect(shopField?.method).toBe("visible_text");
  });

  it("parses specifications from text labels", async () => {
    const specs = parseSpecificationsFromText(`
      Brand: KAW
      Origin: Viet Nam
      Material: ABS
      Size 120 inch
      Pin 5000mAh
      Ho tro 4K
      Android 11
    `);

    expect(specs["Thuong hieu"]).toBe("KAW");
    expect(specs["Xuat xu"]).toBe("Viet Nam");
    expect(specs["Chat lieu"]).toBe("ABS");
    expect(specs["Kich thuoc"]).toBe("120 inch");
    expect(specs.Pin).toBe("5000mAh");
    expect(specs["Do phan giai"]).toContain("4K");
    expect(specs["He dieu hanh"]).toBe("Android 11");
  });

  it("rejects a Shopee page that is not a product detail page", async () => {
    loadFixture("shopee_not_product.html", "https://shopee.vn/category/tech");

    await expect(extractShopeeProduct()).rejects.toThrow("not a supported product page");
  });

  it("removes duplicate and spam features", () => {
    const features = extractFeatures(
      rawProduct({
        description: "Ho tro 4K\nHo tro 4K\nNhan voucher moi ngay\nAndroid 11\nMien phi van chuyen",
      }),
    );

    expect(features.filter((feature) => feature === "Ho tro 4K")).toHaveLength(1);
    expect(features.some((feature) => /voucher|van chuyen/i.test(feature))).toBe(false);
    expect(features.length).toBeLessThanOrEqual(8);
    expect(features.every((feature) => feature.length <= 90)).toBe(true);
  });

  it("keeps the source URL in raw_text", () => {
    const payload = normalizeShopeeToAutoToolPayload(rawProduct());

    expect(payload.raw_text).toContain(`URL: ${PRODUCT_URL}`);
  });
});

function loadFixture(name: string, url: string) {
  const html = readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");
  const dom = new JSDOM(html, { url });
  vi.stubGlobal("window", dom.window);
  vi.stubGlobal("document", dom.window.document);
  return dom;
}

function rawProduct(overrides: Partial<ShopeeRawProduct> = {}): ShopeeRawProduct {
  return {
    source: "shopee",
    url: PRODUCT_URL,
    extractedAt: "2026-06-08T00:00:00.000Z",
    name: "May chieu KAW XMAX10",
    brand: "KAW",
    price: "1.990.000d",
    description: "Ho tro 4K\nAndroid 11\nDo sang cao",
    specifications: {
      "Thuong hieu": "KAW",
      "Do sang": "10000 Lumens",
    },
    shopName: "KAW Official",
    images: ["https://down-vn.img.susercontent.com/file/basic.jpg"],
    warnings: [],
    ...overrides,
  };
}
