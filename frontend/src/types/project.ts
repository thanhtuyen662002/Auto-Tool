export interface ProductSpec {
  name: string;
  value: string;
}

export interface ProductInfo {
  name: string;
  brand: string;
  description: string;
  features: string[];
  specs?: ProductSpec[];
  cta: string;
  validation_warnings?: string[];
  hashtag_suggestions?: string[];
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
  preferred_variant_ids?: string[];
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

export interface SubtitleStyle {
  font_family: string;
  font_size: number;
  font_color: string;
  stroke_color: string;
  stroke_width: number;
  shadow_enabled: boolean;
  shadow_color: string;
  shadow_opacity: number;
  max_chars_per_line: number;
  max_lines: number;
  position: string;
}

export interface OverlayStyle {
  enabled: boolean;
  height_ratio: number;
  background_color: string;
  background_opacity: number;
  border_radius: number;
  padding_x: number;
  padding_y: number;
  accent_color?: string | null;
  show_accent_bar: boolean;
  show_soft_gradient: boolean;
  style_type: string;
}

export interface VisualStyleSettings {
  preset_id: string;
  custom_overrides?: Record<string, unknown> | null;
}

export interface IndustrySettings {
  preset_id?: string | null;
}

export interface CropSafetySettings {
  enabled: boolean;
  mode: 'auto_safe' | 'center_crop' | 'fit_blur_background' | string;
  allow_blur_background: boolean;
  reduce_zoom_on_risk: boolean;
  reduce_overlay_on_risk: boolean;
}

export interface CacheSettings {
  enabled: boolean;
  cache_media_metadata: boolean;
  cache_segment_scoring: boolean;
  cache_crop_safety: boolean;
  cache_tts: boolean;
  cache_overlay_assets: boolean;
  clear_cache_before_render: boolean;
}

export interface SourceMediaSettings {
  respect_user_exclusions: boolean;
  prefer_favorite_segments: boolean;
  allow_excluded_fallback: boolean;
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
  visual_style?: VisualStyleSettings;
  industry?: IndustrySettings | null;
  crop_safety?: CropSafetySettings;
  cache?: CacheSettings;
  source_media?: SourceMediaSettings;
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
  industry_preset_id?: string | null;
  caption_tone?: string | null;
  hashtag_suggestions_used?: string[];
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
  cache_summary?: CacheSummary | null;
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
  crop_safety?: CropSafetyOutputSummary;
  log_file?: string;
  error?: string;
  warnings?: string[];
  errors?: string[];
}

export interface JobResult {
  outputs: JobOutput[];
}

export interface CacheSummary {
  enabled: boolean;
  hits: number;
  misses: number;
  cache_size_mb: number;
  media_metadata_hits?: number;
  media_metadata_misses?: number;
  segment_score_hits?: number;
  segment_score_misses?: number;
  crop_safety_hits?: number;
  crop_safety_misses?: number;
  tts_hits?: number;
  tts_misses?: number;
  overlay_hits?: number;
  overlay_misses?: number;
  cache_lookup_seconds?: number;
  cache_read_seconds?: number;
  cache_write_seconds?: number;
  cache_saved_estimated_seconds?: number;
  items: Record<string, number>;
}

export interface ClearCacheResponse {
  success: boolean;
  message: string;
}

export type MediaReviewStatus = 'pending' | 'good' | 'bad' | 'excluded' | 'favorite';
export type SegmentReviewStatus = 'pending' | 'good' | 'bad' | 'excluded' | 'favorite';

export interface SourceMediaItem {
  id: string;
  project_id: string;
  path: string;
  filename: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  format_name: string;
  orientation: string;
  aspect_ratio: string;
  quality_score?: number | null;
  segment_count: number;
  usable_segment_count: number;
  rejected_segment_count: number;
  review_status: MediaReviewStatus;
  user_note?: string | null;
  warnings: string[];
  errors: string[];
  created_at: string;
  updated_at: string;
}

export interface SegmentReviewItem {
  id: string;
  project_id: string;
  segment_id: string;
  source_media_id: string;
  source_path: string;
  start: number;
  end: number;
  duration: number;
  overall_score: number;
  brightness_score?: number | null;
  sharpness_score?: number | null;
  motion_score?: number | null;
  freeze_score?: number | null;
  stability_score?: number | null;
  crop_safety_score?: number | null;
  crop_mode?: string | null;
  tags: string[];
  reject_reasons: string[];
  warnings: string[];
  review_status: SegmentReviewStatus;
  user_note?: string | null;
  preview_thumbnail_path?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SourceMediaSummary {
  total_media: number;
  good_media: number;
  excluded_media: number;
  bad_media: number;
  total_segments: number;
  usable_segments: number;
  excluded_segments: number;
  favorite_segments: number;
  average_media_score?: number | null;
  average_segment_score?: number | null;
}

export interface SourceMediaResponse {
  summary: SourceMediaSummary;
  items: SourceMediaItem[];
}

export interface SegmentReviewResponse {
  items: SegmentReviewItem[];
}

export interface UpdateSourceMediaReviewResponse {
  success: boolean;
  item: SourceMediaItem;
}

export interface UpdateSegmentReviewResponse {
  success: boolean;
  item: SegmentReviewItem;
}

export interface BulkSegmentReviewResponse {
  success: boolean;
  updated_count: number;
}

export interface CropSafetyOutputSummary {
  average_score?: number | null;
  fallback_to_blur_background: number;
  warnings: string[];
}

export interface CropSafetyAnalyzeResponse {
  success: boolean;
  error?: string;
  total_clips_analyzed?: number;
  average_crop_safety_score?: number;
  fallback_to_blur_background?: number;
  warnings_summary?: Record<string, number>;
  report_path?: string;
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

export interface VisualStylePreset {
  id: string;
  name: string;
  description: string;
  category: string;
  recommended_for: string[];
  subtitle?: SubtitleStyle | null;
  overlay?: OverlayStyle | null;
}

export interface VisualStylePresetsResponse {
  presets: VisualStylePreset[];
}

export interface VisualStylePreviewResponse {
  success: boolean;
  preview_image_path: string;
  preview_image_url?: string | null;
}

export interface IndustryPreset {
  id: string;
  name: string;
  description: string;
  recommended_for: string[];
  default_video_style: string;
  default_edit_strength: string;
  timeline_template_id: string;
  visual_style_preset_id: string;
  script_variation_mode: string;
  preferred_script_variant_ids: string[];
  default_tts_voice: string;
  caption_tone: string;
  hashtag_suggestions: string[];
  render_defaults: Record<string, unknown>;
  notes: string[];
}

export interface IndustryPresetsResponse {
  presets: IndustryPreset[];
}

export interface ApplyIndustryPresetOptions {
  apply_visual_style: boolean;
  apply_timeline: boolean;
  apply_script_variation: boolean;
  apply_tts_voice: boolean;
  apply_edit_strength: boolean;
}

export interface ApplyIndustryPresetResponse {
  success: boolean;
  project_id: string;
  preset_id: string;
  updated_config: ProjectConfig;
}

export type ProductImportInputType = 'manual' | 'text' | 'json' | 'txt' | 'csv';

export interface RawProductInput {
  input_type: ProductImportInputType;
  raw_text?: string | null;
  file_path?: string | null;
  file_content?: string | null;
  source_name?: string | null;
}

export interface ProductInfoNormalized {
  name: string;
  brand?: string | null;
  description: string;
  features: string[];
  specs: ProductSpec[];
  cta: string;
  industry_preset_id?: string | null;
  hashtag_suggestions: string[];
  warnings: string[];
  missing_fields: string[];
  confidence_score: number;
}

export interface ProductValidationIssue {
  field: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
  suggestion?: string | null;
}

export interface ProductImportResult {
  success: boolean;
  product?: ProductInfoNormalized | null;
  issues: ProductValidationIssue[];
  raw_preview?: string | null;
}

export interface UpdateProjectProductInfoResponse {
  success: boolean;
  project_id: string;
  product: ProductInfoNormalized;
  updated_config: ProjectConfig;
}

export interface SafetyIssue {
  severity: 'info' | 'warning' | 'error';
  category: string;
  field?: string | null;
  message: string;
  suggestion?: string | null;
}

export interface SafetyCheckResult {
  passed: boolean;
  issues: SafetyIssue[];
  warnings_count: number;
  errors_count: number;
}
