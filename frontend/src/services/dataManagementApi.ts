import { backendUrl } from './api';

export type DataCategory =
  | 'config'
  | 'database'
  | 'projects'
  | 'outputs'
  | 'exports'
  | 'subtitles'
  | 'logs'
  | 'cache'
  | 'temp'
  | 'backups'
  | 'frontend';

export type StorageItem = {
  path: string;
  category: DataCategory;
  exists: boolean;
  size_bytes: number;
  file_count: number;
  folder_count: number;
  last_modified?: string | null;
  safe_to_cleanup: boolean;
  description?: string | null;
};

export type StorageUsageReport = {
  total_size_bytes: number;
  items: StorageItem[];
  warnings: string[];
};

export type StorageUsageResponse = {
  success: boolean;
  data: StorageUsageReport;
  warnings: string[];
  errors: string[];
};

export type BackupRequest = {
  include_config: boolean;
  include_database: boolean;
  include_projects: boolean;
  include_outputs: boolean;
  include_exports: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  backup_name?: string | null;
  backup_folder?: string | null;
};

export type BackupResult = {
  success: boolean;
  backup_path?: string | null;
  manifest_path?: string | null;
  size_bytes: number;
  included_categories: DataCategory[];
  warnings: string[];
  errors: string[];
};

export type BackupListItem = {
  path: string;
  manifest_path?: string | null;
  size_bytes: number;
  created_at?: string | null;
  included_categories: DataCategory[];
};

export type BackupListResponse = {
  success: boolean;
  items: BackupListItem[];
  warnings: string[];
  errors: string[];
};

export type BackupInspectResult = {
  success: boolean;
  backup_path: string;
  manifest?: Record<string, unknown> | null;
  included_categories: DataCategory[];
  file_count: number;
  size_bytes: number;
  warnings: string[];
  errors: string[];
};

export type RestoreRequest = {
  backup_path: string;
  restore_config: boolean;
  restore_database: boolean;
  restore_projects: boolean;
  restore_outputs: boolean;
  restore_exports: boolean;
  restore_subtitles: boolean;
  restore_logs: boolean;
  create_pre_restore_backup: boolean;
  overwrite_existing: boolean;
};

export type RestoreResult = {
  success: boolean;
  restored_categories: DataCategory[];
  pre_restore_backup_path?: string | null;
  warnings: string[];
  errors: string[];
};

export type CleanupTarget =
  | 'launcher_logs'
  | 'debug_logs'
  | 'temp_files'
  | 'cache_files'
  | 'preview_frames'
  | 'failed_partial_renders'
  | 'old_exports';

export type CleanupRequest = {
  targets: CleanupTarget[];
  older_than_days: number;
  dry_run: boolean;
  confirm_delete: boolean;
};

export type CleanupPreviewItem = {
  path: string;
  target: CleanupTarget;
  size_bytes: number;
  file_count: number;
  reason: string;
};

export type CleanupResult = {
  success: boolean;
  dry_run: boolean;
  deleted_size_bytes: number;
  deleted_file_count: number;
  preview_items: CleanupPreviewItem[];
  warnings: string[];
  errors: string[];
};

export function getStorageUsage(): Promise<StorageUsageResponse> {
  return request('/api/local-app/storage-usage');
}

export function createBackup(payload: BackupRequest): Promise<BackupResult> {
  return request('/api/local-app/backup', { method: 'POST', body: JSON.stringify(payload) });
}

export function listBackups(): Promise<BackupListResponse> {
  return request('/api/local-app/backups');
}

export function inspectBackup(backupPath: string): Promise<BackupInspectResult> {
  return request('/api/local-app/backup/inspect', { method: 'POST', body: JSON.stringify({ backup_path: backupPath }) });
}

export function restoreBackup(payload: RestoreRequest): Promise<RestoreResult> {
  return request('/api/local-app/restore', { method: 'POST', body: JSON.stringify(payload) });
}

export function previewCleanup(payload: CleanupRequest): Promise<CleanupResult> {
  return request('/api/local-app/cleanup/preview', { method: 'POST', body: JSON.stringify(payload) });
}

export function runCleanup(payload: CleanupRequest): Promise<CleanupResult> {
  return request('/api/local-app/cleanup/run', { method: 'POST', body: JSON.stringify(payload) });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(backendUrl(path), {
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    ...init,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') message = payload.detail;
      else if (payload.detail) message = JSON.stringify(payload.detail);
    } catch {
      // Keep HTTP status when response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

