export type JsonObject = Record<string, unknown>;

export function cleanText(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const cleaned = value.replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  return cleaned || undefined;
}

export function textFromSelectors(selectors: string[], root: Document | Element = document): string | undefined {
  for (const selector of selectors) {
    const node = root.querySelector(selector);
    const text = cleanText(node?.textContent);
    if (text) {
      return text;
    }
  }
  return undefined;
}

export function allTextCandidates(root: Document | Element = document): string[] {
  const selectors = [
    "h1",
    "h2",
    "section",
    "article",
    "main",
    "[role='main']",
    "[data-testid]",
    "div",
  ];
  const values: string[] = [];
  for (const selector of selectors) {
    for (const element of Array.from(root.querySelectorAll(selector)).slice(0, 400)) {
      const text = cleanText(element.textContent);
      if (text && text.length >= 3 && text.length <= 1200) {
        values.push(text);
      }
    }
  }
  return uniqueStrings(values);
}

export function uniqueStrings(values: Array<string | undefined | null>, limit = 50): string[] {
  const cleaned: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const text = cleanText(value);
    if (!text) {
      continue;
    }
    const key = text.toLocaleLowerCase();
    if (seen.has(key)) {
      continue;
    }
    cleaned.push(text);
    seen.add(key);
    if (cleaned.length >= limit) {
      break;
    }
  }
  return cleaned;
}

export function metaContent(names: string[]): string | undefined {
  for (const name of names) {
    const selector = `meta[property='${cssEscape(name)}'], meta[name='${cssEscape(name)}']`;
    const value = cleanText(document.querySelector<HTMLMetaElement>(selector)?.content);
    if (value) {
      return value;
    }
  }
  return undefined;
}

export function absoluteUrl(value: string | undefined): string | undefined {
  const cleaned = cleanText(value);
  if (!cleaned) {
    return undefined;
  }
  try {
    return new URL(cleaned, window.location.href).href;
  } catch {
    return undefined;
  }
}

export function readJsonLdObjects(): JsonObject[] {
  const scripts = Array.from(document.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]'));
  return scripts.flatMap((script) => flattenJsonLd(safeJsonParse(script.textContent || "")));
}

export function safeJsonParse(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

export function firstDefined<T>(...values: Array<T | undefined>): T | undefined {
  return values.find((value) => value !== undefined);
}

export function srcFromImage(image: HTMLImageElement): string | undefined {
  const source =
    image.currentSrc ||
    image.src ||
    image.dataset.src ||
    image.getAttribute("data-src") ||
    image.getAttribute("src");
  return absoluteUrl(source || firstSrcSetUrl(image.srcset || image.getAttribute("srcset") || undefined));
}

function flattenJsonLd(value: unknown): JsonObject[] {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => flattenJsonLd(item));
  }
  if (typeof value !== "object") {
    return [];
  }
  const object = value as JsonObject;
  const graph = object["@graph"];
  const nested = Array.isArray(graph) ? graph.flatMap((item) => flattenJsonLd(item)) : [];
  return [object, ...nested];
}

function firstSrcSetUrl(value: string | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return value
    .split(",")
    .map((part) => part.trim().split(/\s+/)[0])
    .find(Boolean);
}

function cssEscape(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}
