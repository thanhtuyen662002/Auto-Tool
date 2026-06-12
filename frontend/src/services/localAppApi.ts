import { backendUrl } from './api';

export type LocalAppConfig = {
  default_source_folder: string;
  default_output_folder: string;
  default_music_folder: string;
  auto_open_browser: boolean;
  enable_open_folder: boolean;
  max_recent_items: number;
  backend_host: string;
  backend_port: number;
  frontend_host: string;
  frontend_port: number;
  production_single_port: boolean;
  serve_frontend_dist: boolean;
  single_port_url: string;
  frontend_dist_path: string;
};

export type LocalRecentPaths = {
  source_folders: string[];
  output_folders: string[];
  music_folders: string[];
};

export type LocalSystemCheckItem = {
  name: string;
  status: 'ready' | 'missing' | 'optional' | 'warning';
  message: string;
  path?: string | null;
  version?: string | null;
  required: boolean;
};

export type LocalSystemCheck = {
  ready: boolean;
  platform: string;
  checks: LocalSystemCheckItem[];
};

export type LocalDesktopAction = {
  success: boolean;
  path: string;
  message: string;
};

export type LocalFrontendStatus = {
  success: boolean;
  data: {
    mode: 'production_single_port' | 'development';
    enabled: boolean;
    dist_exists: boolean;
    index_html_exists: boolean;
    assets_exists: boolean;
    dist_path: string;
    served_by_backend: boolean;
    single_port_url: string;
    message: string;
  };
  warnings: string[];
  errors: string[];
};

export const DEFAULT_LOCAL_APP_CONFIG: LocalAppConfig = {
  default_source_folder: '',
  default_output_folder: './examples/outputs',
  default_music_folder: '',
  auto_open_browser: true,
  enable_open_folder: true,
  max_recent_items: 5,
  backend_host: '127.0.0.1',
  backend_port: 8000,
  frontend_host: '127.0.0.1',
  frontend_port: 5173,
  production_single_port: true,
  serve_frontend_dist: true,
  single_port_url: 'http://127.0.0.1:8000',
  frontend_dist_path: 'frontend/dist',
};

export function getLocalAppConfig(): Promise<LocalAppConfig> {
  return request('/api/local-app/config');
}

export function saveLocalAppConfig(config: LocalAppConfig): Promise<LocalAppConfig> {
  return request('/api/local-app/config', { method: 'PUT', body: JSON.stringify(config) });
}

export function getLocalSystemCheck(): Promise<LocalSystemCheck> {
  return request('/api/local-app/system-check');
}

export function getFrontendStatus(): Promise<LocalFrontendStatus> {
  return request('/api/local-app/frontend-status');
}

export function getRecentPaths(): Promise<LocalRecentPaths> {
  return request('/api/local-app/recent-paths');
}

export function addRecentSourceFolder(path: string): Promise<LocalRecentPaths> {
  return addRecentPath('source', path);
}

export function addRecentOutputFolder(path: string): Promise<LocalRecentPaths> {
  return addRecentPath('output', path);
}

export function addRecentMusicFolder(path: string): Promise<LocalRecentPaths> {
  return addRecentPath('music', path);
}

export function openFolder(path: string): Promise<LocalDesktopAction> {
  return desktopAction('/api/local-app/open-folder', path);
}

export function revealFile(path: string): Promise<LocalDesktopAction> {
  return desktopAction('/api/local-app/reveal-file', path);
}

function addRecentPath(kind: 'source' | 'output' | 'music', path: string): Promise<LocalRecentPaths> {
  return request(`/api/local-app/recent-paths/${kind}`, {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

function desktopAction(endpoint: string, path: string): Promise<LocalDesktopAction> {
  return request(endpoint, { method: 'POST', body: JSON.stringify({ path }) });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(backendUrl(path), {
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json() as { detail?: unknown };
      if (typeof payload.detail === 'string') message = payload.detail;
    } catch {
      // Keep the HTTP status when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
