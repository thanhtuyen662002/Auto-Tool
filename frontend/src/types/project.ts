export interface ProductInfo {
  name: string;
  brand: string;
  description: string;
  features: string[];
  cta: string;
}

export interface RenderSettings {
  output_count: number;
  duration: number;
  aspect_ratio: string;
  resolution: string;
  fps: number;
}

export interface EffectSettings {
  cut_intensity: number;
  speed_variation: number;
  grain: number;
  zoom_motion: number;
  overlay_height: number;
  subtitle_size: number;
}

export interface AISettings {
  text_model: string;
  tone: string;
  language: string;
  gemini_api_keys?: string[];
}

export interface MusicSettings {
  enabled: boolean;
  source_folder?: string | null;
  source_file?: string | null;
  volume: number;
  fade_in: number;
  fade_out: number;
  duck_under_voice: boolean;
}

export interface TimelineSettings {
  template_id: string;
}

export interface ScriptVariationSettings {
  mode: string;
}

export interface TTSSettings {
  provider: string;
  fallback_provider: string;
  voice: string;
  language: string;
  api_key?: string | null;
  credentials_json_path?: string | null;
  access_token?: string | null;
  rate: string;
  pitch: string;
  volume: string;
  output_format: string;
}

export interface ProjectConfig {
  project_name: string;
  source_folder: string;
  output_folder: string;
  product: ProductInfo;
  render: RenderSettings;
  effects: EffectSettings;
  ai: AISettings;
  music: MusicSettings;
  timeline: TimelineSettings;
  script_variation?: ScriptVariationSettings;
  tts?: TTSSettings;
}

export interface ProjectResponse {
  project_id: string;
  status: string;
}

export interface ProjectDetail {
  project_id: string;
  status: string;
  config: ProjectConfig;
  created_at: string;
  updated_at: string;
}

export interface AppSettings {
  gemini_api_keys: string[];
  google_tts_credentials_json_path?: string | null;
  google_tts_api_key?: string | null;
  google_tts_access_token?: string | null;
}

export interface MediaFile {
  path: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  format_name: string;
}

export interface ScanResponse {
  total_files: number;
  valid_videos: number;
  invalid_files: number;
  media: MediaFile[];
}

export interface SegmentScoringSummary {
  total_segments: number;
  usable_segments: number;
  rejected_segments: number;
  average_score: number;
  rejection_summary: Record<string, number>;
  report_path?: string | null;
}

export interface RenderResponse {
  job_id: string;
  status: string;
}

export interface VoiceoverLine {
  time_hint: string;
  text: string;
}

export interface SubtitleLine {
  start_hint?: number | null;
  end_hint?: number | null;
  text: string;
}

export interface ProductVideoScript {
  variant_style_id?: string | null;
  hook: string;
  voiceover: VoiceoverLine[];
  subtitles: SubtitleLine[];
  cta: string;
  caption: string;
  hashtags: string[];
}

export interface LatestScriptResponse {
  script: ProductVideoScript | null;
}

export interface JobLogItem {
  created_at: string;
  level: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed' | string;
  current_step: string;
  progress: number;
  total_outputs: number;
  completed_outputs: number;
  failed_outputs: number;
  logs: JobLogItem[];
}

export interface JobOutput {
  index: number;
  path: string;
  status: string;
  duration?: number | null;
  visual_video?: string;
  script_file?: string;
  subtitle_file?: string;
  subtitle_ass_file?: string;
  voice_file?: string;
  normalized_voice_file?: string;
  music_file?: string | null;
  tts_provider?: string | null;
  tts_fallback_used?: boolean | null;
  timeline_template?: string | null;
  script_variant_id?: string | null;
  caption?: string | null;
  hashtags?: string[];
  log_file?: string;
  error?: string;
  warnings?: string[];
  errors?: string[];
}

export interface JobResult {
  outputs: JobOutput[];
}

export type OutputReviewStatus = 'pending' | 'good' | 'bad' | 'needs_rerender' | 'ignored';

export interface OutputReviewSummary {
  total_outputs: number;
  good: number;
  review: number;
  needs_rerender: number;
  failed: number;
  bad: number;
  average_overall_score: number;
}

export interface OutputReviewItem {
  output_index: number;
  video_path: string;
  status: string;
  overall_score: number;
  technical_score: number;
  segment_score: number;
  audio_score: number;
  subtitle_score: number;
  timeline_score: number;
  recommended_action: string;
  review_status: OutputReviewStatus;
  user_note?: string | null;
  warnings: string[];
  errors: string[];
}

export interface OutputReviewResponse {
  summary: OutputReviewSummary;
  outputs: OutputReviewItem[];
}

export interface RerenderRequest {
  mode: 'selected' | 'failed_only' | 'needs_rerender' | 'bad_and_failed';
  output_indexes?: number[];
  reuse_script: boolean;
  reuse_timeline: boolean;
  reuse_settings: boolean;
}

export interface RerenderResponse {
  job_id: string;
  status: string;
  rerender_outputs: number[];
}

export interface Preset {
  name: string;
  effects: EffectSettings;
  timeline_template_id?: string | null;
}

export interface TimelineTemplateSummary {
  id: string;
  name: string;
  description: string;
}

export interface TimelineTemplatesResponse {
  templates: TimelineTemplateSummary[];
}

export interface ScriptVariantStyle {
  id: string;
  name: string;
  description: string;
  hook_type: string;
  tone: string;
  cta_style: string;
  best_for_templates: string[];
}

export interface ScriptVariantStylesResponse {
  styles: ScriptVariantStyle[];
}

export interface ScriptVariantSummary {
  output_index: number;
  variant_style_id: string;
  hook: string;
}

export interface GenerateScriptVariantsResponse {
  total_variants: number;
  variants: ScriptVariantSummary[];
  report_path?: string | null;
}

export interface TTSProviderInfo {
  id: string;
  name: string;
  requires_api_key: boolean;
  online: boolean;
  recommended: boolean;
}

export interface TTSProvidersResponse {
  providers: TTSProviderInfo[];
}

export interface TTSVoiceInfo {
  name: string;
  language_codes: string[];
  ssml_gender: string;
  natural_sample_rate_hertz: number;
}

export interface TTSVoicesResponse {
  voices: TTSVoiceInfo[];
}

export type PublishStatus = 'draft' | 'copied' | 'posted' | 'skipped';

export interface ContentBatchSummary {
  total_items: number;
  draft: number;
  copied: number;
  posted: number;
  skipped: number;
}

export interface OutputContentItem {
  id: string;
  project_id: string;
  output_index: number;
  video_path: string;
  hook?: string | null;
  caption: string;
  hashtags: string[];
  cta?: string | null;
  variant_style_id?: string | null;
  timeline_template_id?: string | null;
  publish_status: PublishStatus;
  platform?: string | null;
  user_note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentItemsResponse {
  summary: ContentBatchSummary;
  items: OutputContentItem[];
}

export interface UpdateContentItemResponse {
  success: boolean;
  item: OutputContentItem;
}

export interface ContentExportFile {
  format: string;
  path: string;
}

export interface ContentExportResponse {
  success: boolean;
  files: ContentExportFile[];
}
