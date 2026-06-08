import { afterEach, describe, expect, it, vi } from "vitest";
import { checkAutoToolHealth, sendProductToAutoTool } from "../src/shared/autoToolApi";
import type { AutoToolProductPayload } from "../src/shared/types";

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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Auto Tool API client", () => {
  it("checks health endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok" }),
      }),
    );

    await expect(checkAutoToolHealth("http://localhost:8000")).resolves.toBe(true);
  });

  it("sends product payload to import endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, product: { name: "Test" }, issues: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendProductToAutoTool("http://localhost:8000", payload)).resolves.toMatchObject({ success: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/product-info/import",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("returns a friendly error when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(sendProductToAutoTool("http://localhost:8000", payload)).resolves.toMatchObject({
      success: false,
      error: expect.stringContaining("Could not connect"),
    });
  });
});
