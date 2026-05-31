import type {
  JobResult,
  JobStatus,
  LatestScriptResponse,
  Preset,
  ProductVideoScript,
  ProjectConfig,
  ProjectDetail,
  ProjectResponse,
  RenderResponse,
  OutputReviewResponse,
  OutputReviewStatus,
  RerenderRequest,
  RerenderResponse,
  ScanResponse,
  SegmentScoringSummary,
  GenerateScriptVariantsResponse,
  ScriptVariantStylesResponse,
  TimelineTemplatesResponse,
  TTSProvidersResponse,
  TTSVoicesResponse,
  AppSettings,
  ContentExportResponse,
  ContentItemsResponse,
  OutputContentItem,
  PublishStatus,
  UpdateContentItemResponse,
} from '../types/project';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

export function videoFileUrl(path: string): string {
  return `${API_BASE_URL}/api/files/video?path=${encodeURIComponent(path)}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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

export function createProject(config: ProjectConfig): Promise<ProjectResponse> {
  return request<ProjectResponse>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export function getProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${projectId}`);
}

export function getAppSettings(): Promise<AppSettings> {
  return request<AppSettings>('/api/settings');
}

export function saveAppSettings(settings: AppSettings): Promise<AppSettings> {
  return request<AppSettings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}

export function scanProject(projectId: string): Promise<ScanResponse> {
  return request<ScanResponse>(`/api/projects/${projectId}/scan`, {
    method: 'POST',
  });
}

export function analyzeProjectSegments(projectId: string): Promise<SegmentScoringSummary> {
  return request<SegmentScoringSummary>(`/api/projects/${projectId}/analyze-segments`, {
    method: 'POST',
  });
}

export function startRender(projectId: string, previewOnly: boolean): Promise<RenderResponse> {
  return request<RenderResponse>(`/api/projects/${projectId}/render`, {
    method: 'POST',
    body: JSON.stringify({ preview_only: previewOnly }),
  });
}

export function getLatestScript(projectId: string): Promise<LatestScriptResponse> {
  return request<LatestScriptResponse>(`/api/projects/${projectId}/latest-script`);
}

export function saveProjectScript(
  projectId: string,
  script: ProductVideoScript,
): Promise<LatestScriptResponse> {
  return request<LatestScriptResponse>(`/api/projects/${projectId}/script`, {
    method: 'PUT',
    body: JSON.stringify(script),
  });
}

export function getJobStatus(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${jobId}`);
}

export function getJobResults(jobId: string): Promise<JobResult> {
  return request<JobResult>(`/api/jobs/${jobId}/results`);
}

export function getOutputReview(projectId: string): Promise<OutputReviewResponse> {
  return request<OutputReviewResponse>(`/api/projects/${projectId}/outputs/review`);
}

export function updateOutputReview(
  projectId: string,
  outputIndex: number,
  reviewStatus: OutputReviewStatus,
  userNote?: string | null,
): Promise<{ success: boolean; output_index: number; review_status: OutputReviewStatus }> {
  return request(`/api/projects/${projectId}/outputs/${outputIndex}/review`, {
    method: 'PUT',
    body: JSON.stringify({ review_status: reviewStatus, user_note: userNote ?? null }),
  });
}

export function startRerender(projectId: string, payload: RerenderRequest): Promise<RerenderResponse> {
  return request<RerenderResponse>(`/api/projects/${projectId}/rerender`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getPresets(): Promise<Preset[]> {
  return request<Preset[]>('/api/presets');
}

export function getTimelineTemplates(): Promise<TimelineTemplatesResponse> {
  return request<TimelineTemplatesResponse>('/api/timeline-templates');
}

export function getScriptVariantStyles(): Promise<ScriptVariantStylesResponse> {
  return request<ScriptVariantStylesResponse>('/api/script-variants/styles');
}

export function getTTSProviders(): Promise<TTSProvidersResponse> {
  return request<TTSProvidersResponse>('/api/tts/providers');
}

export function getGoogleCloudTTSVoices(
  auth: {
    apiKey?: string | null;
    credentialsJsonPath?: string | null;
    accessToken?: string | null;
  } = {},
  languageCode = 'vi-VN',
): Promise<TTSVoicesResponse> {
  return request<TTSVoicesResponse>('/api/tts/google-cloud/voices', {
    method: 'POST',
    body: JSON.stringify({
      api_key: auth.apiKey || null,
      credentials_json_path: auth.credentialsJsonPath || null,
      access_token: auth.accessToken || null,
      language_code: languageCode,
    }),
  });
}

export function generateScriptVariants(
  projectId: string,
  outputCount: number,
  timelineTemplateId: string,
): Promise<GenerateScriptVariantsResponse> {
  return request<GenerateScriptVariantsResponse>(`/api/projects/${projectId}/generate-script-variants`, {
    method: 'POST',
    body: JSON.stringify({
      output_count: outputCount,
      timeline_template_id: timelineTemplateId,
    }),
  });
}

export function getProjectContent(projectId: string): Promise<ContentItemsResponse> {
  return request<ContentItemsResponse>(`/api/projects/${projectId}/content`);
}

export function updateProjectContentItem(
  projectId: string,
  outputIndex: number,
  payload: Partial<
    Pick<OutputContentItem, 'hook' | 'caption' | 'cta' | 'platform' | 'user_note'>
  > & { hashtags?: string | string[]; publish_status?: PublishStatus },
): Promise<{ success: boolean; item: OutputContentItem }> {
  return request<UpdateContentItemResponse>(`/api/projects/${projectId}/content/${outputIndex}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function markContentCopied(
  projectId: string,
  outputIndex: number,
): Promise<{ success: boolean; item: OutputContentItem }> {
  return request<UpdateContentItemResponse>(`/api/projects/${projectId}/content/${outputIndex}/mark-copied`, {
    method: 'POST',
  });
}

export function markContentPosted(
  projectId: string,
  outputIndex: number,
  platform?: string | null,
): Promise<{ success: boolean; item: OutputContentItem }> {
  return request<UpdateContentItemResponse>(`/api/projects/${projectId}/content/${outputIndex}/mark-posted`, {
    method: 'POST',
    body: JSON.stringify({ platform: platform || null }),
  });
}

export function exportProjectContent(
  projectId: string,
  formats: string[],
): Promise<ContentExportResponse> {
  return request<ContentExportResponse>(`/api/projects/${projectId}/content/export`, {
    method: 'POST',
    body: JSON.stringify({ formats }),
  });
}
