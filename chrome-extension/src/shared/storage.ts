import type { AutoToolProductPayload } from "./types";
import { normalizeBaseUrl } from "./validators";

const API_BASE_URL_KEY = "autoToolApiBaseUrl";
const FRONTEND_BASE_URL_KEY = "autoToolFrontendBaseUrl";
const LAST_PAYLOAD_KEY = "lastAutoToolShopeePayload";

export const DEFAULT_API_BASE_URL = "http://localhost:8000";
export const DEFAULT_FRONTEND_BASE_URL = "http://localhost:5173";

function chromeStorageGet<T>(key: string): Promise<T | undefined> {
  return chrome.storage.local.get(key).then((items) => items[key] as T | undefined);
}

export async function getApiBaseUrl(): Promise<string> {
  const stored = await chromeStorageGet<string>(API_BASE_URL_KEY);
  return normalizeBaseUrl(stored || DEFAULT_API_BASE_URL);
}

export async function setApiBaseUrl(value: string): Promise<string> {
  const normalized = normalizeBaseUrl(value);
  await chrome.storage.local.set({ [API_BASE_URL_KEY]: normalized });
  return normalized;
}

export async function getFrontendBaseUrl(): Promise<string> {
  const stored = await chromeStorageGet<string>(FRONTEND_BASE_URL_KEY);
  return normalizeBaseUrl(stored || DEFAULT_FRONTEND_BASE_URL);
}

export async function setFrontendBaseUrl(value: string): Promise<string> {
  const normalized = normalizeBaseUrl(value);
  await chrome.storage.local.set({ [FRONTEND_BASE_URL_KEY]: normalized });
  return normalized;
}

export function getLastPayload(): Promise<AutoToolProductPayload | undefined> {
  return chromeStorageGet<AutoToolProductPayload>(LAST_PAYLOAD_KEY);
}

export function setLastPayload(payload: AutoToolProductPayload): Promise<void> {
  return chrome.storage.local.set({ [LAST_PAYLOAD_KEY]: payload });
}

export function clearSavedData(): Promise<void> {
  return chrome.storage.local.remove(LAST_PAYLOAD_KEY);
}
