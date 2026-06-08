import { extractShopeeProduct } from "./extractors/shopeeExtractor";
import type { ExtractProductMessage, ExtractProductResponse } from "../shared/types";

chrome.runtime.onMessage.addListener(
  (message: ExtractProductMessage, _sender, sendResponse: (response: ExtractProductResponse) => void) => {
    if (message.type !== "EXTRACT_SHOPEE_PRODUCT") {
      return false;
    }

    extractShopeeProduct()
      .then((product) => {
        sendResponse({ success: true, product });
      })
      .catch((error) => {
        sendResponse({
          success: false,
          error: error instanceof Error ? error.message : "Could not extract Shopee product data.",
        });
      });

    return true;
  },
);
