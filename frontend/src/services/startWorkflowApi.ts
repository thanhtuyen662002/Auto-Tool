import {
  browsePath,
  getSystemDependencies,
  listDouyinReupPresets,
  scanDouyinReupFolder,
  startDouyinOneClickBatch,
} from '../api/client';
import type {
  BrowsePathMode,
  DouyinOneClickBatchRequest,
  DouyinOneClickBatchResponse,
  DouyinReupPreset,
  DouyinReupScanResponse,
  SystemDependencyStatusResponse,
} from '../types/project';
import { arrayField, numberField, unwrapApiResponse } from '../utils/apiResponse';

export type StartDouyinRequest = DouyinOneClickBatchRequest;
export type StartSilentRequest = DouyinOneClickBatchRequest;

export async function scanDouyinFolder(sourceFolder: string): Promise<DouyinReupScanResponse> {
  const rawResponse = await scanDouyinReupFolder(sourceFolder);
  const response = unwrapApiResponse(rawResponse) ?? rawResponse;
  return {
    total_files: numberField(response.total_files),
    valid_videos: numberField(response.valid_videos),
    invalid_files: numberField(response.invalid_files),
    media: arrayField(response.media),
    errors: arrayField(response.errors),
  };
}

export function startDouyinOneClick(request: StartDouyinRequest): Promise<DouyinOneClickBatchResponse> {
  return startDouyinOneClickBatch(request);
}

export function startSilentOneClick(request: StartSilentRequest): Promise<DouyinOneClickBatchResponse> {
  return startDouyinOneClickBatch(request);
}

export async function getPresets(): Promise<DouyinReupPreset[]> {
  const rawResponse = await listDouyinReupPresets();
  const response = unwrapApiResponse(rawResponse) ?? rawResponse;
  return arrayField(response.presets);
}

export function getHealth(): Promise<SystemDependencyStatusResponse> {
  return getSystemDependencies();
}

export async function browseStartFolder(
  title: string,
  initialPath?: string | null,
  mode: BrowsePathMode = 'folder',
): Promise<string | null> {
  const response = await browsePath({
    mode,
    title,
    initial_path: initialPath || null,
    extensions: [],
  });
  return response.cancelled ? null : response.path ?? null;
}
