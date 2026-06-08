import type { AutoToolImportResponse, AutoToolProductPayload } from "./types";
import { normalizeBaseUrl } from "./validators";

export async function checkAutoToolHealth(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/api/health`, {
      method: "GET",
      mode: "cors",
    });
    if (!response.ok) {
      return false;
    }
    const payload = (await response.json()) as { status?: string };
    return payload.status === "ok";
  } catch {
    return false;
  }
}

export async function sendProductToAutoTool(
  baseUrl: string,
  payload: AutoToolProductPayload,
): Promise<AutoToolImportResponse> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/api/product-info/import`, {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = (await response.json().catch(() => ({}))) as AutoToolImportResponse & { detail?: string };
    if (!response.ok) {
      return {
        success: false,
        issues: data.issues,
        error: data.error || data.detail || `Auto Tool API returned HTTP ${response.status}.`,
      };
    }
    return data;
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof TypeError
          ? "Could not connect to Auto Tool. Open the backend at http://localhost:8000 and try again."
          : "Auto Tool API request failed.",
    };
  }
}
