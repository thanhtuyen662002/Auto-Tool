const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim() || '/api';

export const API_BASE_URL = configuredBase.replace(/\/$/, '') || '/api';

const API_ORIGIN = API_BASE_URL.endsWith('/api')
  ? API_BASE_URL.slice(0, -4)
  : API_BASE_URL;

export function backendUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_ORIGIN}${normalizedPath}`;
}

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return backendUrl(normalizedPath.startsWith('/api/') || normalizedPath === '/api' ? normalizedPath : `/api${normalizedPath}`);
}
