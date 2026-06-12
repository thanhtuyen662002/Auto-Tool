import { getSystemDependencies } from '../api/client';
import { backendUrl } from './api';
import { getFrontendStatus, type LocalFrontendStatus } from './localAppApi';
import type { SystemDependencyStatusResponse } from '../types/project';
import { unwrapApiResponse } from '../utils/apiResponse';

export type SystemStatusValue = 'ready' | 'missing' | 'optional' | 'unknown';

export type NormalizedSystemStatus = {
  backend: 'connected' | 'offline' | 'unknown';
  version?: string;
  capabilities?: Record<string, boolean>;
  ffmpeg: SystemStatusValue;
  ffprobe: SystemStatusValue;
  translation: SystemStatusValue;
  ocr: SystemStatusValue;
  tts: SystemStatusValue;
  outputFolder: SystemStatusValue;
  localServer: SystemStatusValue;
  localServerMode?: LocalFrontendStatus['data']['mode'];
  singlePortUrl?: string;
  dependencies?: SystemDependencyStatusResponse | null;
};

export type HealthResponse = {
  status?: string;
  version?: string;
  capabilities?: Record<string, boolean>;
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(backendUrl('/api/health'), {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) throw new Error('Backend offline');
  const payload = (await response.json()) as HealthResponse;
  return unwrapApiResponse(payload) ?? payload;
}

export async function getSystemStatus(): Promise<NormalizedSystemStatus> {
  try {
    const [health, dependencies, frontendStatus] = await Promise.all([
      getHealth().catch(() => null),
      getSystemDependencies().then((response) => unwrapApiResponse(response) ?? response).catch(() => null),
      getFrontendStatus().catch(() => null),
    ]);

    return normalizeSystemStatus(health, dependencies, frontendStatus);
  } catch {
    return offlineStatus();
  }
}

export function normalizeSystemStatus(
  health: HealthResponse | null,
  dependencies: SystemDependencyStatusResponse | null,
  frontendStatus: LocalFrontendStatus | null = null,
): NormalizedSystemStatus {
  return {
    backend: health ? 'connected' : 'offline',
    version: health?.version,
    capabilities: health?.capabilities,
    ffmpeg: dependencies ? statusFromPath(dependencies.ffmpeg_path) : 'unknown',
    ffprobe: dependencies ? statusFromPath(dependencies.ffprobe_path) : 'unknown',
    translation: inferTranslationStatus(health),
    ocr: dependencies ? (dependencies.ocr_available ? 'ready' : 'optional') : 'unknown',
    tts: dependencies ? (dependencies.piper_path && dependencies.piper_model_path ? 'ready' : 'optional') : 'unknown',
    outputFolder: 'unknown',
    localServer: frontendStatus ? (frontendStatus.data.served_by_backend ? 'ready' : 'missing') : 'unknown',
    localServerMode: frontendStatus?.data.mode,
    singlePortUrl: frontendStatus?.data.single_port_url,
    dependencies,
  };
}

export function offlineStatus(): NormalizedSystemStatus {
  return {
    backend: 'offline',
    ffmpeg: 'unknown',
    ffprobe: 'unknown',
    translation: 'unknown',
    ocr: 'unknown',
    tts: 'unknown',
    outputFolder: 'unknown',
    localServer: 'unknown',
    dependencies: null,
  };
}

function statusFromPath(path?: string | null): SystemStatusValue {
  return path ? 'ready' : 'missing';
}

function inferTranslationStatus(health: HealthResponse | null): SystemStatusValue {
  if (!health) return 'unknown';
  if (health.capabilities && typeof health.capabilities.translation === 'boolean') {
    return health.capabilities.translation ? 'ready' : 'missing';
  }
  return 'unknown';
}
