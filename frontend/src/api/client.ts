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
  ApplyIndustryPresetOptions,
  ApplyIndustryPresetResponse,
  ContentExportResponse,
  ContentItemsResponse,
  OutputContentItem,
  PublishStatus,
  UpdateContentItemResponse,
  VisualStylePresetsResponse,
  VisualStylePreviewResponse,
  IndustryPreset,
  IndustryPresetsResponse,
  ProductImportResult,
  ProductInfoNormalized,
  ProductDraft,
  ProductDraftApplyResponse,
  ProductDraftListResponse,
  ProductDraftUpdateRequest,
  ProductAssetListResponse,
  ProductAssetRole,
  ProductAssetsImportResponse,
  AttachDraftAssetsResponse,
  ProjectListResponse,
  CreateProjectFromDraftRequest,
  CreateProjectFromDraftResponse,
  RawProductInput,
  SafetyCheckResult,
  CropSafetyAnalyzeResponse,
  UpdateProjectProductInfoResponse,
  CacheSummary,
  ClearCacheResponse,
  BulkSegmentReviewResponse,
  MediaReviewStatus,
  SegmentReviewResponse,
  SegmentReviewStatus,
  SourceMediaResponse,
  UpdateSegmentReviewResponse,
  UpdateSourceMediaReviewResponse,
  BrowsePathRequest,
  BrowsePathResponse,
  SystemDependencyStatusResponse,
  DouyinApplyPresetRequest,
  DouyinApplyPresetResponse,
  DouyinOneClickBatchRequest,
  DouyinOneClickBatchResponse,
  DouyinReupJobResultsResponse,
  DouyinOcrTestRequest,
  DouyinOcrTestResponse,
  DouyinPresetRecommendationResponse,
  DouyinReupPreset,
  DouyinReupPresetListResponse,
  DouyinReupProcessRequest,
  DouyinReupProcessResponse,
  DouyinReupScanResponse,
  DouyinRetryFailedRequest,
  DouyinRetryFailedResponse,
  DouyinRetryWithPresetRequest,
  SilentReupDetectResponse,
  SilentReupPlanResponse,
  SilentReupRenderResponse,
  SilentCaptionIndustriesResponse,
  SilentCaptionTemplateListResponse,
  SilentReupReviewDocumentResponse,
  SilentVisualTagReportResponse,
  SilentVisualTagVocabulary,
  CreateExportPackRequest,
  FinalOutputQAJobResponse,
  PlatformExportPackResponse,
  PlatformTarget,
  ReferenceSummaryResponse,
  StoryboardRequest,
  StoryboardResponse,
  VideoPromptPackRequest,
  VideoPromptPackResponse,
  ApproveSubtitleDocumentRequest,
  RenderApprovedSubtitleDocumentsRequest,
  RenderSubtitleReviewDocumentRequest,
  SaveSubtitleReviewRequest,
  SubtitleDocumentQualityReport,
  SubtitleQualityFlaggedLinesResponse,
  SubtitleRewriteSuggestionResponse,
  ApplySubtitleRewriteResponse,
  BulkRewriteFlaggedLinesRequest,
  BulkSubtitleRewriteResponse,
  GenerateSubtitleRewriteRequest,
  SubtitleRewriteSuggestionsResponse,
  SubtitleReviewDocument,
  SubtitleReviewDocumentListResponse,
  SubtitleReviewLine,
  SubtitleReviewRenderResponse,
  UpdateSubtitleLineRequest,
} from '../types/project';
import { backendUrl } from '../services/api';

export function videoFileUrl(path: string): string {
  return backendUrl(`/api/files/video?path=${encodeURIComponent(path)}`);
}

export function assetFileUrl(pathOrUrl: string): string {
  if (pathOrUrl.startsWith('/')) return backendUrl(pathOrUrl);
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  return backendUrl(`/api/files/image?path=${encodeURIComponent(pathOrUrl)}`);
}

export function thumbnailFileUrl(path: string): string {
  return backendUrl(`/api/files/thumbnail?path=${encodeURIComponent(path)}`);
}

export function productAssetFileUrl(assetId: string): string {
  return backendUrl(`/api/product-assets/${encodeURIComponent(assetId)}/file`);
}

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

export function createProject(config: ProjectConfig): Promise<ProjectResponse> {
  return request<ProjectResponse>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export function getProject(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${projectId}`);
}

export function listProjects(): Promise<ProjectListResponse> {
  return request<ProjectListResponse>('/api/projects');
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

export function browsePath(payload: BrowsePathRequest): Promise<BrowsePathResponse> {
  return request<BrowsePathResponse>('/api/system/browse-path', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function finalOutputQAReportUrl(path: string): string {
  return backendUrl(`/api/final-output-qa/report?path=${encodeURIComponent(path)}`);
}

export function getSystemDependencies(): Promise<SystemDependencyStatusResponse> {
  return request<SystemDependencyStatusResponse>('/api/system/dependencies');
}

export function scanProject(projectId: string): Promise<ScanResponse> {
  return request<ScanResponse>(`/api/projects/${projectId}/scan`, {
    method: 'POST',
  });
}

export function scanDouyinReupFolder(sourceFolder: string): Promise<DouyinReupScanResponse> {
  return request<DouyinReupScanResponse>('/api/douyin-reup/scan', {
    method: 'POST',
    body: JSON.stringify({ source_folder: sourceFolder }),
  });
}

export function testDouyinHardsubOcr(payload: DouyinOcrTestRequest): Promise<DouyinOcrTestResponse> {
  return request<DouyinOcrTestResponse>('/api/douyin-reup/ocr-test', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listDouyinReupPresets(): Promise<DouyinReupPresetListResponse> {
  return request<DouyinReupPresetListResponse>('/api/douyin-reup/presets');
}

export function getDouyinReupPreset(presetId: string): Promise<DouyinReupPreset> {
  return request<DouyinReupPreset>(`/api/douyin-reup/presets/${encodeURIComponent(presetId)}`);
}

export function applyDouyinReupPreset(payload: DouyinApplyPresetRequest): Promise<DouyinApplyPresetResponse> {
  return request<DouyinApplyPresetResponse>('/api/douyin-reup/apply-preset', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function recommendDouyinReupPreset(sourceFolder: string): Promise<DouyinPresetRecommendationResponse> {
  return request<DouyinPresetRecommendationResponse>('/api/douyin-reup/recommend-preset', {
    method: 'POST',
    body: JSON.stringify({ source_folder: sourceFolder }),
  });
}

export function startDouyinReupProcess(
  payload: DouyinReupProcessRequest,
): Promise<DouyinReupProcessResponse> {
  return request<DouyinReupProcessResponse>('/api/douyin-reup/process', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function startDouyinOneClickBatch(
  payload: DouyinOneClickBatchRequest,
): Promise<DouyinOneClickBatchResponse> {
  return request<DouyinOneClickBatchResponse>('/api/douyin-reup/one-click', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getDouyinReupJobResults(jobId: string): Promise<DouyinReupJobResultsResponse> {
  return request<DouyinReupJobResultsResponse>(`/api/douyin-reup/jobs/${jobId}/results`);
}

export function detectSilentReupVideos(sourceFolder: string): Promise<SilentReupDetectResponse> {
  return request<SilentReupDetectResponse>('/api/silent-reup/detect', {
    method: 'POST',
    body: JSON.stringify({ source_folder: sourceFolder }),
  });
}

export function buildSilentReupPlan(payload: {
  video_path: string;
  settings?: Record<string, unknown>;
  product_context?: Record<string, unknown>;
}): Promise<SilentReupPlanResponse> {
  return request<SilentReupPlanResponse>('/api/silent-reup/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function renderSilentReupPlan(planId: string, settings: Record<string, unknown> = {}): Promise<SilentReupRenderResponse> {
  return request<SilentReupRenderResponse>('/api/silent-reup/render', {
    method: 'POST',
    body: JSON.stringify({ plan_id: planId, settings }),
  });
}

export function listSilentCaptionIndustries(): Promise<SilentCaptionIndustriesResponse> {
  return request<SilentCaptionIndustriesResponse>('/api/silent-caption-templates/industries');
}

export function listSilentCaptionTemplates(params: {
  industry?: string;
  intent?: string;
  strategy?: string;
} = {}): Promise<SilentCaptionTemplateListResponse> {
  const query = new URLSearchParams();
  if (params.industry) query.set('industry', params.industry);
  if (params.intent) query.set('intent', params.intent);
  if (params.strategy) query.set('strategy', params.strategy);
  const suffix = query.size ? `?${query.toString()}` : '';
  return request<SilentCaptionTemplateListResponse>(`/api/silent-caption-templates${suffix}`);
}

export function regenerateSilentReupCaptions(
  planId: string,
  payload: {
    industry: string;
    tone: string;
    strategy?: string;
    use_visual_tags?: boolean;
    respect_user_tag_overrides?: boolean;
  },
): Promise<SilentReupPlanResponse> {
  return request<SilentReupPlanResponse>(`/api/silent-reup/plans/${planId}/regenerate-captions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getSilentVisualTagVocabulary(): Promise<SilentVisualTagVocabulary> {
  return request<SilentVisualTagVocabulary>('/api/silent-reup/visual-tags/vocabulary');
}

export function generateSilentVisualTags(planId: string): Promise<SilentVisualTagReportResponse> {
  return request<SilentVisualTagReportResponse>(`/api/silent-reup/plans/${planId}/visual-tags`, {
    method: 'POST',
  });
}

export function getSilentVisualTags(planId: string): Promise<SilentVisualTagReportResponse> {
  return request<SilentVisualTagReportResponse>(`/api/silent-reup/plans/${planId}/visual-tags`);
}

export function updateSilentSegmentVisualTags(
  planId: string,
  segmentId: string,
  payload: {
    tags: string[];
    primary_industry?: string | null;
    primary_scene?: string | null;
    primary_action?: string | null;
  },
): Promise<SilentReupPlanResponse> {
  return request<SilentReupPlanResponse>(`/api/silent-reup/plans/${planId}/segments/${segmentId}/tags`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function createSilentReupReviewDocument(planId: string): Promise<SilentReupReviewDocumentResponse> {
  return request<SilentReupReviewDocumentResponse>(`/api/silent-reup/plans/${planId}/review-document`, {
    method: 'POST',
  });
}

export function retryFailedDouyinReupJob(
  jobId: string,
  payload: DouyinRetryFailedRequest,
): Promise<DouyinRetryFailedResponse> {
  return request<DouyinRetryFailedResponse>(`/api/douyin-reup/jobs/${jobId}/retry-failed`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function retryDouyinReupJobWithPreset(
  jobId: string,
  payload: DouyinRetryWithPresetRequest,
): Promise<DouyinRetryFailedResponse> {
  return request<DouyinRetryFailedResponse>(`/api/douyin-reup/jobs/${jobId}/retry-with-preset`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function runFinalOutputQAForJob(
  jobId: string,
  platformTarget: PlatformTarget,
): Promise<FinalOutputQAJobResponse> {
  return request<FinalOutputQAJobResponse>(`/api/final-output-qa/jobs/${jobId}/check`, {
    method: 'POST',
    body: JSON.stringify({ platform_target: platformTarget }),
  });
}

export function createDouyinExportPack(
  jobId: string,
  payload: CreateExportPackRequest,
): Promise<PlatformExportPackResponse> {
  return request<PlatformExportPackResponse>(`/api/douyin-reup/jobs/${jobId}/export-pack`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getDouyinExportPack(jobId: string): Promise<PlatformExportPackResponse> {
  return request<PlatformExportPackResponse>(`/api/douyin-reup/jobs/${jobId}/export-pack`);
}

export function openDouyinExportPack(jobId: string): Promise<{ success: boolean; path: string }> {
  return request<{ success: boolean; path: string }>(`/api/douyin-reup/jobs/${jobId}/export-pack/open`, {
    method: 'POST',
  });
}

export function listSubtitleReviewDocuments(filters: {
  project_id?: string | null;
  job_id?: string | null;
  status?: string | null;
} = {}): Promise<SubtitleReviewDocumentListResponse> {
  const params = new URLSearchParams();
  if (filters.project_id) params.set('project_id', filters.project_id);
  if (filters.job_id) params.set('job_id', filters.job_id);
  if (filters.status) params.set('status', filters.status);
  const query = params.toString();
  return request<SubtitleReviewDocumentListResponse>(`/api/subtitle-review/documents${query ? `?${query}` : ''}`);
}

export function getSubtitleReviewDocument(documentId: string): Promise<SubtitleReviewDocument> {
  return request<SubtitleReviewDocument>(`/api/subtitle-review/documents/${documentId}`);
}

export function updateSubtitleReviewLine(
  documentId: string,
  lineIndex: number,
  payload: UpdateSubtitleLineRequest,
): Promise<SubtitleReviewLine> {
  return request<SubtitleReviewLine>(`/api/subtitle-review/documents/${documentId}/lines/${lineIndex}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function saveSubtitleReviewDocument(
  documentId: string,
  payload: SaveSubtitleReviewRequest,
): Promise<SubtitleReviewDocument> {
  return request<SubtitleReviewDocument>(`/api/subtitle-review/documents/${documentId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function approveSubtitleReviewDocument(
  documentId: string,
  payload: ApproveSubtitleDocumentRequest,
): Promise<SubtitleReviewDocument> {
  return request<SubtitleReviewDocument>(`/api/subtitle-review/documents/${documentId}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getSubtitleQualityReport(documentId: string): Promise<SubtitleDocumentQualityReport> {
  return request<SubtitleDocumentQualityReport>('/api/subtitle-review/documents/' + documentId + '/quality');
}

export function refreshSubtitleQualityReport(documentId: string): Promise<SubtitleDocumentQualityReport> {
  return request<SubtitleDocumentQualityReport>(
    '/api/subtitle-review/documents/' + documentId + '/quality/refresh',
    { method: 'POST' },
  );
}

export function getSubtitleQualityFlaggedLines(documentId: string): Promise<SubtitleQualityFlaggedLinesResponse> {
  return request<SubtitleQualityFlaggedLinesResponse>(
    '/api/subtitle-review/documents/' + documentId + '/quality/flagged-lines',
  );
}

export function suggestSubtitleLineRewrite(
  documentId: string,
  lineIndex: number,
  style = 'short_natural_vietnamese',
): Promise<SubtitleRewriteSuggestionResponse> {
  return request<SubtitleRewriteSuggestionResponse>(
    '/api/subtitle-review/documents/' + documentId + '/lines/' + lineIndex + '/suggest-rewrite',
    {
      method: 'POST',
      body: JSON.stringify({ style }),
    },
  );
}

export function generateSubtitleRewriteSuggestions(
  documentId: string,
  lineIndex: number,
  payload: GenerateSubtitleRewriteRequest,
): Promise<SubtitleRewriteSuggestionsResponse> {
  return request<SubtitleRewriteSuggestionsResponse>(
    `/api/subtitle-review/documents/${documentId}/lines/${lineIndex}/rewrite-suggestions`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export function applySubtitleRewrite(
  documentId: string,
  lineIndex: number,
  suggestionId: string,
): Promise<ApplySubtitleRewriteResponse> {
  return request<ApplySubtitleRewriteResponse>(
    `/api/subtitle-review/documents/${documentId}/lines/${lineIndex}/apply-rewrite`,
    {
      method: 'POST',
      body: JSON.stringify({ suggestion_id: suggestionId, refresh_quality_score: true }),
    },
  );
}

export function rewriteFlaggedSubtitleLines(
  documentId: string,
  payload: BulkRewriteFlaggedLinesRequest,
): Promise<BulkSubtitleRewriteResponse> {
  return request<BulkSubtitleRewriteResponse>(
    `/api/subtitle-review/documents/${documentId}/rewrite-flagged-lines`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

export function renderSubtitleReviewDocument(
  documentId: string,
  payload: RenderSubtitleReviewDocumentRequest,
): Promise<SubtitleReviewRenderResponse> {
  return request<SubtitleReviewRenderResponse>(`/api/subtitle-review/documents/${documentId}/render`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function renderApprovedSubtitleReviewDocuments(
  payload: RenderApprovedSubtitleDocumentsRequest,
): Promise<SubtitleReviewRenderResponse> {
  return request<SubtitleReviewRenderResponse>('/api/subtitle-review/render-approved', {
    method: 'POST',
    body: JSON.stringify(payload),
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

export function getVisualStyles(): Promise<VisualStylePresetsResponse> {
  return request<VisualStylePresetsResponse>('/api/visual-styles');
}

export function previewVisualStyle(
  presetId: string,
  sampleText: string,
  resolution = '1080x1920',
): Promise<VisualStylePreviewResponse> {
  return request<VisualStylePreviewResponse>('/api/visual-styles/preview', {
    method: 'POST',
    body: JSON.stringify({
      preset_id: presetId,
      sample_text: sampleText,
      resolution,
    }),
  });
}

export function updateProjectVisualStyle(
  projectId: string,
  presetId: string,
): Promise<{ success: boolean; visual_style: { preset_id: string; custom_overrides?: Record<string, unknown> | null } }> {
  return request(`/api/projects/${projectId}/visual-style`, {
    method: 'PUT',
    body: JSON.stringify({ preset_id: presetId }),
  });
}

export function getIndustryPresets(): Promise<IndustryPresetsResponse> {
  return request<IndustryPresetsResponse>('/api/industry-presets');
}

export function getIndustryPreset(presetId: string): Promise<IndustryPreset> {
  return request<IndustryPreset>(`/api/industry-presets/${presetId}`);
}

export function applyIndustryPresetToProject(
  projectId: string,
  presetId: string,
  options: ApplyIndustryPresetOptions,
): Promise<ApplyIndustryPresetResponse> {
  return request<ApplyIndustryPresetResponse>(`/api/projects/${projectId}/industry-preset`, {
    method: 'PUT',
    body: JSON.stringify({ preset_id: presetId, ...options }),
  });
}

export function importProductInfo(payload: RawProductInput): Promise<ProductImportResult> {
  return request<ProductImportResult>('/api/product-info/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listProductDrafts(filters: {
  status?: string | null;
  source_name?: string | null;
  limit?: number;
  offset?: number;
} = {}): Promise<ProductDraftListResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.source_name) params.set('source_name', filters.source_name);
  if (filters.limit != null) params.set('limit', String(filters.limit));
  if (filters.offset != null) params.set('offset', String(filters.offset));
  const query = params.toString();
  return request<ProductDraftListResponse>(`/api/product-drafts${query ? `?${query}` : ''}`);
}

export function getProductDraft(draftId: string): Promise<ProductDraft> {
  return request<ProductDraft>(`/api/product-drafts/${draftId}`);
}

export function updateProductDraft(draftId: string, payload: ProductDraftUpdateRequest): Promise<ProductDraft> {
  return request<ProductDraft>(`/api/product-drafts/${draftId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function archiveProductDraft(draftId: string): Promise<ProductDraft> {
  return request<ProductDraft>(`/api/product-drafts/${draftId}/archive`, {
    method: 'POST',
  });
}

export function deleteProductDraft(draftId: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/api/product-drafts/${draftId}`, {
    method: 'DELETE',
  });
}

export function clearArchivedProductDrafts(): Promise<{ success: boolean; deleted_count: number }> {
  return request<{ success: boolean; deleted_count: number }>('/api/product-drafts/clear-archived', {
    method: 'POST',
  });
}

export function applyProductDraftToProject(
  draftId: string,
  projectId: string,
): Promise<ProductDraftApplyResponse> {
  return request<ProductDraftApplyResponse>(`/api/product-drafts/${draftId}/apply-to-project/${projectId}`, {
    method: 'POST',
  });
}

export function createProjectFromDraft(
  draftId: string,
  payload: CreateProjectFromDraftRequest,
): Promise<CreateProjectFromDraftResponse> {
  return request<CreateProjectFromDraftResponse>(`/api/product-drafts/${draftId}/create-project`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listProductDraftAssets(draftId: string): Promise<ProductAssetListResponse> {
  return request<ProductAssetListResponse>(`/api/product-drafts/${draftId}/assets`);
}

export function importProductDraftAssets(
  draftId: string,
  payload: {
    project_id?: string | null;
    selected_asset_urls?: string[] | null;
    download_selected?: boolean;
  },
): Promise<ProductAssetsImportResponse> {
  return request<ProductAssetsImportResponse>(`/api/product-drafts/${draftId}/assets/import`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function attachProductDraftAssetsToProject(
  draftId: string,
  projectId: string,
  selectedAssetIds?: string[] | null,
): Promise<AttachDraftAssetsResponse> {
  return request<AttachDraftAssetsResponse>(`/api/product-drafts/${draftId}/assets/attach-to-project/${projectId}`, {
    method: 'POST',
    body: JSON.stringify({ selected_asset_ids: selectedAssetIds ?? null }),
  });
}

export function listProjectAssets(projectId: string): Promise<ProductAssetListResponse> {
  return request<ProductAssetListResponse>(`/api/projects/${projectId}/assets`);
}

export function generateReferenceSummary(projectId: string): Promise<ReferenceSummaryResponse> {
  return request<ReferenceSummaryResponse>(`/api/projects/${projectId}/reference-summary`, {
    method: 'POST',
  });
}

export function generateStoryboard(
  projectId: string,
  payload: StoryboardRequest,
): Promise<StoryboardResponse> {
  return request<StoryboardResponse>(`/api/projects/${projectId}/storyboard`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function generateVideoPromptPack(
  projectId: string,
  payload: VideoPromptPackRequest,
): Promise<VideoPromptPackResponse> {
  return request<VideoPromptPackResponse>(`/api/projects/${projectId}/video-prompt-pack`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateProductAsset(
  assetId: string,
  payload: { role?: ProductAssetRole | null; is_selected?: boolean | null; user_note?: string | null },
): Promise<ProductAssetsImportResponse> {
  return request<ProductAssetsImportResponse>(`/api/product-assets/${assetId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteProductAsset(assetId: string): Promise<ProductAssetsImportResponse> {
  return request<ProductAssetsImportResponse>(`/api/product-assets/${assetId}`, {
    method: 'DELETE',
  });
}

export function updateProjectProductInfo(
  projectId: string,
  product: ProductInfoNormalized,
): Promise<UpdateProjectProductInfoResponse> {
  return request<UpdateProjectProductInfoResponse>(`/api/projects/${projectId}/product-info`, {
    method: 'PUT',
    body: JSON.stringify({ product }),
  });
}

export function checkProjectSafety(projectId: string): Promise<SafetyCheckResult> {
  return request<SafetyCheckResult>(`/api/projects/${projectId}/safety-check`, {
    method: 'POST',
  });
}

export function analyzeCropSafety(projectId: string): Promise<CropSafetyAnalyzeResponse> {
  return request<CropSafetyAnalyzeResponse>(`/api/projects/${projectId}/crop-safety/analyze`, {
    method: 'POST',
  });
}

export function getProjectCacheSummary(projectId: string): Promise<CacheSummary> {
  return request<CacheSummary>(`/api/projects/${projectId}/cache/summary`);
}

export function clearProjectCache(projectId: string): Promise<ClearCacheResponse> {
  return request<ClearCacheResponse>(`/api/projects/${projectId}/cache/clear`, {
    method: 'POST',
  });
}

export function getSourceMedia(projectId: string): Promise<SourceMediaResponse> {
  return request<SourceMediaResponse>(`/api/projects/${projectId}/source-media`);
}

export function updateSourceMediaReview(
  projectId: string,
  mediaPath: string,
  reviewStatus: MediaReviewStatus,
  userNote?: string | null,
): Promise<UpdateSourceMediaReviewResponse> {
  return request<UpdateSourceMediaReviewResponse>(`/api/projects/${projectId}/source-media/review`, {
    method: 'PUT',
    body: JSON.stringify({
      media_path: mediaPath,
      review_status: reviewStatus,
      user_note: userNote ?? null,
    }),
  });
}

export function getSourceSegments(
  projectId: string,
  filters: { sourcePath?: string | null; status?: string | null; minScore?: number | null; tag?: string | null } = {},
): Promise<SegmentReviewResponse> {
  const params = new URLSearchParams();
  if (filters.sourcePath) params.set('source_path', filters.sourcePath);
  if (filters.status) params.set('status', filters.status);
  if (filters.minScore != null) params.set('min_score', String(filters.minScore));
  if (filters.tag) params.set('tag', filters.tag);
  const query = params.toString();
  return request<SegmentReviewResponse>(`/api/projects/${projectId}/segments${query ? `?${query}` : ''}`);
}

export function updateSegmentReview(
  projectId: string,
  segmentId: string,
  reviewStatus: SegmentReviewStatus,
  userNote?: string | null,
): Promise<UpdateSegmentReviewResponse> {
  return request<UpdateSegmentReviewResponse>(`/api/projects/${projectId}/segments/${segmentId}/review`, {
    method: 'PUT',
    body: JSON.stringify({
      review_status: reviewStatus,
      user_note: userNote ?? null,
    }),
  });
}

export function bulkUpdateSegmentReview(
  projectId: string,
  segmentIds: string[],
  reviewStatus: SegmentReviewStatus,
  userNote?: string | null,
): Promise<BulkSegmentReviewResponse> {
  return request<BulkSegmentReviewResponse>(`/api/projects/${projectId}/segments/bulk-review`, {
    method: 'POST',
    body: JSON.stringify({
      segment_ids: segmentIds,
      review_status: reviewStatus,
      user_note: userNote ?? null,
    }),
  });
}
