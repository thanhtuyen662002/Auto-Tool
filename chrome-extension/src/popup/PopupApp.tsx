import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  buildRawTextFromStructuredData,
  normalizeShopeeToAutoToolPayload,
} from "../content/extractors/normalizeShopeeProduct";
import { checkAutoToolHealth, sendProductToAutoTool } from "../shared/autoToolApi";
import {
  DEFAULT_API_BASE_URL,
  DEFAULT_FRONTEND_BASE_URL,
  clearSavedData,
  getApiBaseUrl,
  getFrontendBaseUrl,
  getLastPayload,
  setApiBaseUrl,
  setFrontendBaseUrl,
  setLastPayload,
} from "../shared/storage";
import type { AutoToolImportResponse, AutoToolProductPayload, ExtractProductResponse } from "../shared/types";
import { isShopeeUrl, normalizeBaseUrl, validateAutoToolPayload } from "../shared/validators";
import "./popup.css";

type ApiStatus = "checking" | "connected" | "not_connected";
type BusyAction = "extract" | "send" | "copy" | "save" | "clear" | undefined;

function PopupApp() {
  const [apiBaseUrl, setApiBaseUrlState] = useState(DEFAULT_API_BASE_URL);
  const [apiInput, setApiInput] = useState(DEFAULT_API_BASE_URL);
  const [frontendBaseUrl, setFrontendBaseUrlState] = useState(DEFAULT_FRONTEND_BASE_URL);
  const [frontendInput, setFrontendInput] = useState(DEFAULT_FRONTEND_BASE_URL);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [currentUrl, setCurrentUrl] = useState<string>();
  const [payload, setPayload] = useState<AutoToolProductPayload>();
  const [busy, setBusy] = useState<BusyAction>();
  const [statusMessage, setStatusMessage] = useState("Ready.");
  const [importResponse, setImportResponse] = useState<AutoToolImportResponse>();

  const validationResult = useMemo(() => validateAutoToolPayload(payload), [payload]);
  const popupState = importResponse?.success ? "Sent" : payload ? "Extracted" : "Ready";
  const isShopeePage = isShopeeUrl(currentUrl);

  useEffect(() => {
    void initializePopup();
  }, []);

  async function initializePopup() {
    const [storedUrl, storedFrontendUrl, storedPayload, tab] = await Promise.all([
      getApiBaseUrl(),
      getFrontendBaseUrl(),
      getLastPayload(),
      getActiveTab(),
    ]);
    setApiBaseUrlState(storedUrl);
    setApiInput(storedUrl);
    setFrontendBaseUrlState(storedFrontendUrl);
    setFrontendInput(storedFrontendUrl);
    setCurrentUrl(tab?.url);
    setPayload(storedPayload);
    await refreshApiHealth(storedUrl);
  }

  async function refreshApiHealth(baseUrl = apiBaseUrl) {
    setApiStatus("checking");
    const connected = await checkAutoToolHealth(baseUrl);
    setApiStatus(connected ? "connected" : "not_connected");
  }

  async function saveApiUrl() {
    setBusy("save");
    try {
      const normalized = await setApiBaseUrl(apiInput);
      setApiBaseUrlState(normalized);
      setApiInput(normalized);
      await refreshApiHealth(normalized);
      setStatusMessage("API URL saved.");
    } finally {
      setBusy(undefined);
    }
  }

  async function saveFrontendUrl() {
    setBusy("save");
    try {
      const normalized = await setFrontendBaseUrl(frontendInput);
      setFrontendBaseUrlState(normalized);
      setFrontendInput(normalized);
      setStatusMessage("Frontend URL saved.");
    } finally {
      setBusy(undefined);
    }
  }

  async function extractProduct() {
    setBusy("extract");
    setImportResponse(undefined);
    try {
      const tab = await getActiveTab();
      setCurrentUrl(tab?.url);
      if (!tab?.id || !isShopeeUrl(tab.url)) {
        setStatusMessage("Trang hien tai chua phai trang Shopee. Hay mo trang chi tiet san pham roi thu lai.");
        return;
      }
      const response = await extractFromTab(tab.id);
      if (!response.success) {
        setStatusMessage(response.error);
        return;
      }
      const nextPayload = normalizeShopeeToAutoToolPayload(response.product);
      setPayload(nextPayload);
      await setLastPayload(nextPayload);
      setStatusMessage("Product info extracted.");
    } catch {
      setStatusMessage("Khong extract duoc du lieu. Shopee DOM co the da thay doi.");
    } finally {
      setBusy(undefined);
    }
  }

  async function sendToAutoTool() {
    if (!payload) {
      return;
    }
    if (!validationResult.valid) {
      setStatusMessage(validationResult.errors[0] || "Payload is not ready to send.");
      return;
    }
    setBusy("send");
    try {
      const connected = await checkAutoToolHealth(apiBaseUrl);
      setApiStatus(connected ? "connected" : "not_connected");
      if (!connected) {
        setStatusMessage("Khong ket noi duoc Auto Tool. Hay mo backend o http://localhost:8000 roi thu lai.");
        return;
      }
      const result = await sendProductToAutoTool(apiBaseUrl, payload);
      setImportResponse(result);
      setStatusMessage(
        result.success && result.draft
          ? `Da luu vao Auto Tool Import Inbox: ${result.draft.title}`
          : result.success
            ? "Sent to Auto Tool."
            : result.error || "Auto Tool API returned an error.",
      );
    } finally {
      setBusy(undefined);
    }
  }

  async function copyJson() {
    if (!payload) {
      return;
    }
    setBusy("copy");
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setStatusMessage("JSON copied.");
    } catch {
      setStatusMessage("Could not copy JSON.");
    } finally {
      setBusy(undefined);
    }
  }

  async function clearPreview() {
    setBusy("clear");
    try {
      await clearSavedData();
      setPayload(undefined);
      setImportResponse(undefined);
      setStatusMessage("Saved preview cleared.");
    } finally {
      setBusy(undefined);
    }
  }

  function updateField(field: "name" | "brand" | "description" | "cta", value: string) {
    setPayload((current) => {
      if (!current) {
        return current;
      }
      const structuredData = {
        ...current.structured_data,
        [field]: value,
      };
      const nextPayload = {
        ...current,
        raw_text: buildRawTextFromStructuredData(structuredData, current.source_url),
        structured_data: structuredData,
      };
      void setLastPayload(nextPayload);
      return nextPayload;
    });
  }

  const product = payload?.structured_data;

  return (
    <main className="popup-shell">
      <header className="popup-header">
        <div>
          <h1>Auto Tool Shopee Extractor</h1>
          <p>{statusMessage}</p>
        </div>
      </header>

      <section className="status-grid">
        <StatusPill label="Extension state" value={popupState} tone={popupState === "Sent" ? "ok" : "neutral"} />
        <StatusPill label="Current page" value={isShopeePage ? "Shopee" : "Not supported"} tone={isShopeePage ? "ok" : "warn"} />
        <StatusPill
          label="Auto Tool API"
          value={apiStatus === "checking" ? "Checking" : apiStatus === "connected" ? "Connected" : "Not connected"}
          tone={apiStatus === "connected" ? "ok" : apiStatus === "checking" ? "neutral" : "warn"}
        />
      </section>

      <section className="settings-row">
        <label htmlFor="apiBaseUrl">Auto Tool API URL</label>
        <div className="input-with-button">
          <input
            id="apiBaseUrl"
            value={apiInput}
            onChange={(event) => setApiInput(event.target.value)}
            onBlur={() => setApiInput(normalizeBaseUrl(apiInput))}
          />
          <button type="button" onClick={saveApiUrl} disabled={busy === "save"}>
            Save
          </button>
        </div>
        <label className="secondary-label" htmlFor="frontendBaseUrl">
          Auto Tool Frontend URL
        </label>
        <div className="input-with-button">
          <input
            id="frontendBaseUrl"
            value={frontendInput}
            onChange={(event) => setFrontendInput(event.target.value)}
            onBlur={() => setFrontendInput(normalizeBaseUrl(frontendInput))}
          />
          <button type="button" onClick={saveFrontendUrl} disabled={busy === "save"}>
            Save
          </button>
        </div>
      </section>

      <section className="action-row">
        <button type="button" className="primary" onClick={extractProduct} disabled={busy === "extract"}>
          {busy === "extract" ? "Extracting" : "Extract Product Info"}
        </button>
        <button type="button" onClick={sendToAutoTool} disabled={!payload || busy === "send" || !validationResult.valid}>
          {busy === "send" ? "Sending" : "Send to Auto Tool"}
        </button>
        <button type="button" onClick={copyJson} disabled={!payload || busy === "copy"}>
          Copy JSON
        </button>
        <button type="button" onClick={() => chrome.tabs.create({ url: apiBaseUrl })}>
          Open Auto Tool
        </button>
        <button type="button" onClick={() => chrome.tabs.create({ url: `${frontendBaseUrl}/import-inbox` })}>
          Open Import Inbox
        </button>
      </section>

      {product ? (
        <section className="preview-panel">
          <div className="preview-head">
            <h2>Preview</h2>
            <button type="button" className="ghost" onClick={clearPreview} disabled={busy === "clear"}>
              Clear Saved Data
            </button>
          </div>

          <div className="field-stack">
            <LabeledInput label="Name" value={product.name} onChange={(value) => updateField("name", value)} />
            <LabeledInput label="Brand" value={product.brand || ""} onChange={(value) => updateField("brand", value)} />
            <LabeledTextarea
              label="Description"
              value={product.description}
              onChange={(value) => updateField("description", value)}
            />
            <LabeledInput label="CTA" value={product.cta} onChange={(value) => updateField("cta", value)} />
          </div>

          <dl className="summary-list">
            <div>
              <dt>Price</dt>
              <dd>{product.price || "N/A"}</dd>
            </div>
            <div>
              <dt>Shop</dt>
              <dd>{product.shop?.name || "N/A"}</dd>
            </div>
            <div>
              <dt>Features</dt>
              <dd>{product.features.length}</dd>
            </div>
            <div>
              <dt>Specs</dt>
              <dd>{product.specs.length}</dd>
            </div>
          </dl>

          <ExtractorQualityPanel payload={payload} validationWarnings={validationResult.warnings} validationErrors={validationResult.errors} />

          {product.features.length > 0 ? (
            <ul className="feature-list">
              {product.features.slice(0, 5).map((feature) => (
                <li key={feature}>{feature}</li>
              ))}
            </ul>
          ) : null}

          {product.shopee?.warnings?.length ? (
            <div className="warning-box">
              {product.shopee.warnings.slice(0, 4).map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}
        </section>
      ) : (
        <section className="empty-panel">No product preview yet.</section>
      )}

      {importResponse ? (
        <section className={importResponse.success ? "result-box success" : "result-box error"}>
          <strong>{importResponse.success ? "Import success" : "Import failed"}</strong>
          {importResponse.draft ? (
            <div className="draft-result">
              <p>Da luu vao Auto Tool Import Inbox</p>
              <p>Draft: {importResponse.draft.title}</p>
              <p>Confidence: {Math.round(importResponse.draft.confidence_score * 100)}%</p>
              <button type="button" onClick={() => chrome.tabs.create({ url: importResponse.import_inbox_url || `${frontendBaseUrl}/import-inbox` })}>
                Open Import Inbox
              </button>
              <button
                type="button"
                onClick={() =>
                  chrome.tabs.create({
                    url: `${importResponse.import_inbox_url || `${frontendBaseUrl}/import-inbox`}?draft=${encodeURIComponent(importResponse.draft!.id)}`,
                  })
                }
              >
                Open Draft
              </button>
            </div>
          ) : null}
          {importResponse.error ? <p>{importResponse.error}</p> : null}
          {importResponse.issues?.length ? <pre>{JSON.stringify(importResponse.issues, null, 2)}</pre> : null}
        </section>
      ) : null}
    </main>
  );
}

function ExtractorQualityPanel({
  payload,
  validationWarnings,
  validationErrors,
}: {
  payload: AutoToolProductPayload;
  validationWarnings: string[];
  validationErrors: string[];
}) {
  const report = payload.extractor_debug;
  const missingFields = report?.fields.filter((field) => !field.valueFound).map((field) => field.field) || [];
  const confidence = report ? Math.round(report.overallConfidence * 100) : undefined;
  const warnings = [...(report?.warnings || []), ...validationWarnings];

  return (
    <div className="warning-box">
      <p>
        Extractor confidence: <strong>{confidence === undefined ? "N/A" : `${confidence}%`}</strong>
      </p>
      {missingFields.length ? <p>Missing fields: {missingFields.join(", ")}</p> : null}
      {validationErrors.length ? <p>Send blocked: {validationErrors.join("; ")}</p> : null}
      {warnings.slice(0, 5).map((warning) => (
        <p key={warning}>{warning}</p>
      ))}
    </div>
  );
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "neutral" }) {
  return (
    <div className={`status-pill ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function LabeledTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <textarea value={value} rows={4} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

async function getActiveTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function extractFromTab(tabId: number): Promise<ExtractProductResponse> {
  try {
    return await sendExtractMessage(tabId);
  } catch {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["src/content/shopeeContentScript.js"],
    });
    return sendExtractMessage(tabId);
  }
}

function sendExtractMessage(tabId: number): Promise<ExtractProductResponse> {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, { type: "EXTRACT_SHOPEE_PRODUCT" }, (response?: ExtractProductResponse) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reject(new Error(error.message));
        return;
      }
      if (!response) {
        reject(new Error("No response from Shopee content script."));
        return;
      }
      resolve(response);
    });
  });
}

createRoot(document.getElementById("root")!).render(<PopupApp />);
