import { backendUrl } from './api';
import type {
  SourceFolderScanRequest,
  SourceFolderScanResult,
  SourceMediaSelectionRequest,
  SourceMediaSelectionResult,
} from '../types/project';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(backendUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json; charset=UTF-8',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') {
        detail = payload.detail;
      } else if (payload.detail) {
        detail = JSON.stringify(payload.detail);
      }
    } catch {
      const text = await response.text();
      if (text) detail = text;
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function scanSourceMedia(payload: SourceFolderScanRequest): Promise<SourceFolderScanResult> {
  return request<SourceFolderScanResult>('/api/source-media/scan', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getSourceMediaFolder(folderId: string): Promise<SourceFolderScanResult> {
  return request<SourceFolderScanResult>(`/api/source-media/folders/${encodeURIComponent(folderId)}`);
}

export function rescanSourceMediaFolder(folderId: string): Promise<SourceFolderScanResult> {
  return request<SourceFolderScanResult>(`/api/source-media/folders/${encodeURIComponent(folderId)}/rescan`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export function createSourceMediaSelection(payload: SourceMediaSelectionRequest): Promise<SourceMediaSelectionResult> {
  return request<SourceMediaSelectionResult>('/api/source-media/selections', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getSourceMediaSelection(selectionId: string): Promise<SourceMediaSelectionResult> {
  return request<SourceMediaSelectionResult>(`/api/source-media/selections/${encodeURIComponent(selectionId)}`);
}

export function sourceMediaThumbnailUrl(folderId: string, mediaId: string): string {
  return backendUrl(`/api/source-media/thumbnails/${encodeURIComponent(folderId)}/${encodeURIComponent(mediaId)}`);
}
