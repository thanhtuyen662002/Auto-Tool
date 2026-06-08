export type ExtractorDebugMethod =
  | "json_ld"
  | "meta"
  | "dom_selector"
  | "script_state"
  | "visible_text"
  | "fallback"
  | "manual";

export type ExtractorFieldDebug = {
  field: string;
  valueFound: boolean;
  valuePreview?: string;
  method: ExtractorDebugMethod;
  confidence: number;
  warnings: string[];
};

export type ShopeeExtractorDebugReport = {
  url: string;
  extractedAt: string;
  pageType: "product" | "unknown" | "unsupported";
  fields: ExtractorFieldDebug[];
  overallConfidence: number;
  warnings: string[];
};

export type ShopeeRawProduct = {
  source: "shopee";
  url: string;
  extractedAt: string;

  productId?: string;
  shopId?: string;

  name?: string;
  brand?: string;
  price?: string;
  priceMin?: string;
  priceMax?: string;
  originalPrice?: string;
  discount?: string;

  rating?: string;
  soldCount?: string;
  reviewCount?: string;

  shopName?: string;
  shopLocation?: string;

  images?: string[];
  videoUrls?: string[];

  categoryBreadcrumbs?: string[];

  description?: string;
  specifications?: Record<string, string>;
  variations?: Array<{
    name: string;
    options: string[];
  }>;

  shippingInfo?: string;
  vouchers?: string[];

  rawTextBlocks?: string[];

  warnings?: string[];
  extractorDebug?: ShopeeExtractorDebugReport;
};

export type AutoToolProductPayload = {
  input_type: "shopee_extension";
  source_name: "shopee";
  source_url: string;
  save_to_inbox: true;
  raw_text: string;
  structured_data: {
    name: string;
    brand?: string;
    description: string;
    features: string[];
    specs: Array<{
      name: string;
      value: string;
    }>;
    cta: string;
    price?: string;
    images?: string[];
    variations?: Array<{
      name: string;
      options: string[];
    }>;
    shop?: {
      name?: string;
      location?: string;
    };
    shopee?: ShopeeRawProduct;
  };
  extractor_debug?: ShopeeExtractorDebugReport;
};

export type AutoToolImportResponse = {
  success: boolean;
  project_id?: string;
  product?: unknown;
  issues?: unknown[];
  source?: {
    name?: string;
    url?: string;
  };
  draft?: {
    id: string;
    title: string;
    status: string;
    confidence_score: number;
  } | null;
  import_inbox_url?: string | null;
  error?: string;
};

export type ExtractProductMessage = {
  type: "EXTRACT_SHOPEE_PRODUCT";
};

export type ExtractProductResponse =
  | {
      success: true;
      product: ShopeeRawProduct;
    }
  | {
      success: false;
      error: string;
    };
