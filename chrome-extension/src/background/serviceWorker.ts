chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get("autoToolApiBaseUrl").then((items) => {
    if (!items.autoToolApiBaseUrl) {
      chrome.storage.local.set({ autoToolApiBaseUrl: "http://localhost:8000" });
    }
  });
  chrome.storage.local.get("autoToolFrontendBaseUrl").then((items) => {
    if (!items.autoToolFrontendBaseUrl) {
      chrome.storage.local.set({ autoToolFrontendBaseUrl: "http://localhost:5173" });
    }
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "AUTO_TOOL_EXTENSION_PING") {
    return false;
  }
  sendResponse({ ok: true });
  return false;
});
