import { describe, expect, it } from "vitest";
import type { AutoToolProductPayload } from "../src/shared/types";
import { validateAutoToolPayload } from "../src/shared/validators";

describe("validateAutoToolPayload", () => {
  it("marks payload missing name as invalid", () => {
    const result = validateAutoToolPayload(validPayload({ name: "" }));

    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Product name is required.");
  });

  it("accepts a valid Shopee extension payload", () => {
    const result = validateAutoToolPayload(validPayload());

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("warns for optional extraction gaps", () => {
    const result = validateAutoToolPayload(
      validPayload({
        brand: "",
        specs: [],
        images: [],
        features: ["Ho tro 4K"],
        description: "Mo ta ngan",
      }),
    );

    expect(result.valid).toBe(true);
    expect(result.warnings).toContain("Brand is missing.");
    expect(result.warnings).toContain("Specifications are missing.");
    expect(result.warnings).toContain("Product images are missing.");
    expect(result.warnings).toContain("Description is short.");
    expect(result.warnings).toContain("Fewer than 2 features were extracted.");
  });
});

function validPayload(
  overrides: Partial<AutoToolProductPayload["structured_data"]> = {},
): AutoToolProductPayload {
  const structuredData: AutoToolProductPayload["structured_data"] = {
    name: "May chieu KAW XMAX10",
    brand: "KAW",
    description: "May chieu mini ho tro 4K, Android 11 va do sang cao.",
    features: ["Ho tro 4K", "Android 11", "Do sang cao"],
    specs: [{ name: "Do sang", value: "10000 Lumens" }],
    cta: "Xem chi tiet san pham tren Shopee",
    price: "1.990.000d",
    images: ["https://down-vn.img.susercontent.com/file/basic.jpg"],
    ...overrides,
  };
  return {
    input_type: "shopee_extension",
    source_name: "shopee",
    source_url: "https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
    save_to_inbox: true,
    raw_text: "Ten san pham: May chieu KAW XMAX10\nURL: https://shopee.vn/May-chieu-KAW-XMAX10-i.123.456",
    structured_data: structuredData,
  };
}
