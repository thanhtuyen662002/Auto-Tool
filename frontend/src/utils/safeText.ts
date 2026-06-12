export function getSafeText(value: unknown, fallback = 'Chưa có dữ liệu'): string {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return fallback;
}

export function getSafePath(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

export function basenameSafe(path: unknown, fallback = 'Chưa có tên file'): string {
  const safePath = getSafePath(path);
  if (!safePath) return fallback;
  return safePath.split(/[\\/]/).filter(Boolean).pop() || fallback;
}

export function compactTextList(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return values
    .map((value) => (typeof value === 'string' ? value.trim() : ''))
    .filter(Boolean);
}
