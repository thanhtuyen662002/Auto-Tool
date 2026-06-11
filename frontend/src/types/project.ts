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
  overlay_mode?: 'preset' | 'none' | 'custom' | string;
  custom_overlay_path?: string | null;
  custom_overlay_height_percent?: number | null;
  custom_overlay_fit_mode?: 'cover' | 'contain' | 'stretch' | string;
}

export interface DouyinReupSettings {
  enabled: boolean;
  preset_id?: string | null;
  preset_name?: string | null;
  source_language: string;
  target_language: string;
  translation_style: string;
  subtitle_position: string;
  translation_provider: string;
  subtitle_source_priority: string[];
  use_sidecar_srt: boolean;
  use_embedded_subtitle: boolean;
  use_asr_if_no_subtitle: boolean;
  asr_provider: string;
  asr_model_size: string;
  asr_device: string;
  asr_vad_filter: boolean;
  asr_subtitle_offset_seconds: number;
  use_ocr_if_asr_failed: boolean;
  use_ocr_if_no_subtitle: boolean;
  ocr_provider: string;
  ocr_language: string;
  ocr_sample_fps: number;
  ocr_region_mode: 'bottom_auto' | 'middle_lower' | 'full_frame' | 'manual' | string;
  ocr_manual_region?: { x: number; y: number; width: number; height: number } | null;
  ocr_min_confidence: number;
  ocr_dedupe_similarity: number;
  ocr_min_text_length: number;
  ocr_merge_gap_ms: number;
  ocr_min_duration_ms: number;
  ocr_max_duration_ms: number;
  prefer_ocr_over_asr_when_text_visible: boolean;
  visual_style_preset_id: string;
  burn_subtitle: boolean;
  add_overlay: boolean;
  keep_original_audio: boolean;
  add_bgm: boolean;
  music_folder?: string | null;
  bgm_volume: number;
  original_audio_volume: number;
  duck_bgm_when_voice: boolean;
  resolution: string;
  fps: number;
  process_mode: 'all' | 'selected' | 'first_n' | string;
  max_videos?: number | null;
  selected_video_paths: string[];
  keep_temp: boolean;
  review_subtitles_before_render: boolean;
  auto_render_after_translation: boolean;
  auto_mark_low_quality_lines: boolean;
  enable_subtitle_rewrite_suggestions: boolean;
  auto_generate_rewrite_for_flagged_lines: boolean;
  auto_apply_safe_rewrites: boolean;
  default_rewrite_style: SubtitleRewriteStyle;
  enable_silent_immersive_mode: boolean;
  silent_mode_detection: boolean;
  silent_mode_strategy: 'chill_immersive' | 'product_review_voiceover' | 'sales_recut' | string;
  detect_speech_presence: boolean;
  speech_detection_threshold: number;
  use_visual_segments_for_silent_video: boolean;
  silent_segment_duration_min: number;
  silent_segment_duration_max: number;
  generate_visual_captions: boolean;
  visual_caption_language: string;
  visual_caption_style: string;
  silent_caption_tone: 'natural' | 'cute' | 'clean_review' | 'sales_light' | 'chill' | string;
  generate_voiceover_for_silent_video: boolean;
  silent_voiceover_provider: string;
  silent_voiceover_voice: string;
  keep_immersive_original_audio: boolean;
  immersive_original_audio_volume: number;
  add_bgm_for_silent_video: boolean;
  immersive_bgm_volume: number;
  silent_review_before_render: boolean;
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

export interface ProjectAssetSettings {
  main_product_asset_id?: string | null;
  reference_asset_ids: string[];
  poster_asset_ids: string[];
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
  assets?: ProjectAssetSettings;
  douyin_reup?: DouyinReupSettings | null;
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

export type BrowsePathMode = 'file' | 'folder';

export interface BrowsePathRequest {
  mode: BrowsePathMode;
  title?: string | null;
  initial_path?: string | null;
  extensions?: string[];
}

export interface BrowsePathResponse {
  path?: string | null;
  cancelled: boolean;
}

export interface SystemDependencyStatusResponse {
  ffmpeg_path?: string | null;
  ffprobe_path?: string | null;
  piper_path?: string | null;
  piper_model_path?: string | null;
  piper_config_path?: string | null;
  ocr_provider?: string | null;
  ocr_available: boolean;
  ocr_message?: string | null;
  warnings: string[];
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

export interface DouyinVideoItem {
  path: string;
  filename: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  has_audio: boolean;
  sidecar_srt_path?: string | null;
  embedded_subtitle_found: boolean;
  status: string;
  warnings: string[];
  errors: string[];
}

export interface DouyinReupScanResponse {
  total_files: number;
  valid_videos: number;
  invalid_files: number;
  media: DouyinVideoItem[];
  errors: string[];
}

export interface DouyinReupProcessRequest {
  project_name: string;
  source_folder: string;
  output_folder: string;
  settings: DouyinReupSettings;
}

export interface DouyinReupProcessResponse {
  project_id: string;
  job_id: string;
  status: string;
}

export interface DouyinReupPreset {
  id: string;
  name: string;
  description: string;
  recommended_for: string[];
  not_recommended_for: string[];
  settings: DouyinReupSettings;
  ui_badge: string;
  is_default: boolean;
}

export interface DouyinReupPresetListResponse {
  presets: DouyinReupPreset[];
}

export interface DouyinApplyPresetRequest {
  preset_id: string;
  current_settings?: DouyinReupSettings | null;
  overrides?: Record<string, unknown>;
}

export interface DouyinApplyPresetResponse {
  preset: DouyinReupPreset;
  settings: DouyinReupSettings;
}

export interface DouyinOneClickBatchRequest {
  project_name: string;
  source_folder: string;
  output_folder: string;
  preset_id?: string;
  bgm_folder?: string | null;
  visual_style_preset_id?: string | null;
  process_mode?: 'all_videos' | 'first_n' | 'selected';
  max_videos?: number | null;
  selected_video_paths?: string[];
  review_subtitles_before_render?: boolean | null;
  auto_render_after_translation?: boolean | null;
  product_context?: Record<string, unknown>;
  advanced_overrides?: Record<string, unknown>;
}

export interface DouyinOneClickBatchResponse {
  project_id: string;
  job_id: string;
  status: string;
  preset_id: string;
  preset_name: string;
  total_outputs: number;
}

export interface DouyinPresetRecommendationResponse {
  preset_id: string;
  preset_name: string;
  reason: string;
  confidence: number;
  signals: Record<string, unknown>;
}

export interface DouyinOutputResult {
  index: number;
  path: string;
  status: string;
  source_video: string;
  preset_id?: string | null;
  preset_name?: string | null;
  subtitle_source?: string | null;
  source_srt_file?: string | null;
  translated_srt_file?: string | null;
  corrected_srt_file?: string | null;
  subtitle_ass_file?: string | null;
  corrected_ass_file?: string | null;
  overlay_file?: string | null;
  bgm_file?: string | null;
  log_file?: string | null;
  subtitle_review_document_id?: string | null;
  reup_mode?: string | null;
  silent_strategy?: string | null;
  speech_score?: number | null;
  caption_source?: string | null;
  silent_plan_file?: string | null;
  voiceover_file?: string | null;
  voiceover_script_file?: string | null;
  voiceover_subtitle_file?: string | null;
  ocr_debug_json_path?: string | null;
  ocr_frame_count?: number;
  ocr_detected_line_count?: number;
  ocr_average_confidence?: number;
  ocr_provider?: string | null;
  ocr_region_mode?: string | null;
  failed_step?: string | null;
  error_message?: string | null;
  can_retry?: boolean;
  duration?: number | null;
  durations?: Record<string, number>;
  retry_history?: Array<Record<string, string | null>>;
  final_output_qa?: FinalOutputQASummary | null;
  warnings: string[];
  errors: string[];
}

export interface DouyinReupSummary {
  project_name: string;
  output_folder: string;
  total_videos: number;
  processed_outputs: number;
  successful_outputs: number;
  failed_outputs: number;
  warnings_count: number;
  subtitle_sources: Record<string, number>;
  failed_items: Array<{ index: number | string; reason: string }>;
  outputs: DouyinOutputResult[];
  subtitle_review?: {
    enabled: boolean;
    documents_created: number;
    approved: number;
    pending: number;
  };
  silent_immersive?: {
    enabled: boolean;
    videos_detected_silent: number;
    videos_processed_silent: number;
    strategies: Record<string, number>;
    caption_sources?: Record<string, number>;
  };
  success?: number;
  failed?: number;
  needs_review?: number;
  rendered?: number;
  failure_breakdown?: Record<string, number>;
  performance?: {
    scan_seconds: number;
    average_asr_seconds_per_video: number;
    average_ocr_seconds_per_video?: number;
    average_translation_seconds_per_video: number;
    average_render_seconds_per_video: number;
    total_runtime_seconds: number;
    slowest_step: string;
  };
  ocr_summary?: {
    videos_attempted: number;
    videos_success: number;
    average_confidence: number;
  };
  preset?: {
    id?: string | null;
    name?: string | null;
  };
  settings_snapshot?: Partial<DouyinReupSettings>;
  subtitle_rewrite?: {
    enabled: boolean;
    suggestions_created: number;
    suggestions_applied: number;
    auto_applied?: number;
    average_quality_improvement: number;
  };
  final_output_qa?: FinalOutputQABatchSummary;
  summary_file?: string | null;
}

export type PlatformTarget = 'tiktok' | 'instagram_reels' | 'youtube_shorts' | 'generic_vertical';
export type FinalOutputQAStatus = 'passed' | 'passed_with_warnings' | 'failed';

export interface FinalOutputQAIssue {
  issue_type: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  suggestion?: string | null;
}

export interface FinalOutputQASummary {
  status: FinalOutputQAStatus;
  score: number;
  report_path?: string | null;
  issues: FinalOutputQAIssue[];
}

export interface FinalOutputQAReport extends FinalOutputQASummary {
  id: string;
  job_id?: string | null;
  project_id?: string | null;
  video_id?: string | null;
  platform_target: PlatformTarget;
  output_video_path: string;
  probe: Record<string, unknown>;
  audio?: Record<string, unknown> | null;
  subtitle_visibility?: Record<string, unknown> | null;
  created_at: string;
}

export interface FinalOutputQABatchSummary {
  platform_target?: PlatformTarget;
  total_checked: number;
  total?: number;
  passed: number;
  passed_with_warnings: number;
  failed: number;
  average_score: number;
  issue_breakdown?: Record<string, number>;
  summary_path?: string;
}

export interface FinalOutputQAJobResponse {
  success: boolean;
  reports: FinalOutputQAReport[];
  summary: FinalOutputQABatchSummary;
}

export interface ExportPackItem {
  label: string;
  path: string;
  file_type: string;
  exists: boolean;
}

export interface PlatformExportPack {
  id: string;
  job_id?: string | null;
  project_id?: string | null;
  platform_target: PlatformTarget;
  output_dir: string;
  items: ExportPackItem[];
  caption_txt_path?: string | null;
  caption_csv_path?: string | null;
  posting_checklist_path?: string | null;
  qa_summary_path?: string | null;
  manifest_path?: string | null;
  created_at: string;
}

export interface CreateExportPackRequest {
  platform_target: PlatformTarget;
  output_dir?: string | null;
  copy_videos: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  include_captions: boolean;
  include_posting_checklist: boolean;
  output_indexes: number[];
}

export interface PlatformExportPackResponse {
  success: boolean;
  export_pack: PlatformExportPack;
}

export interface DouyinOcrTestRequest {
  video_path: string;
  settings: Partial<DouyinReupSettings>;
}

export interface DouyinOcrTestResponse {
  success: boolean;
  result?: Record<string, unknown> | null;
  error?: string | null;
}

export interface DouyinRetryFailedRequest {
  retry_steps: string[];
  settings?: Partial<DouyinReupSettings>;
}

export interface DouyinRetryWithPresetRequest {
  preset_id: string;
  video_ids?: string[];
  retry_steps?: string[];
  settings?: Partial<DouyinReupSettings>;
  advanced_overrides?: Record<string, unknown>;
}

export interface DouyinRetryFailedResponse {
  job_id: string;
  status: string;
  retry_outputs: number;
}

export type SubtitleReviewStatus = 'pending' | 'reviewed' | 'needs_fix' | 'approved';
export type SubtitleQualitySeverity = 'info' | 'warning' | 'critical';

export interface SubtitleQualityIssue {
  issue_type: string;
  severity: SubtitleQualitySeverity;
  message: string;
  suggestion?: string | null;
}

export interface SubtitleLineQualityScore {
  line_index: number;
  score: number;
  severity: SubtitleQualitySeverity;
  needs_review: boolean;
  source_text?: string | null;
  translated_text: string;
  edited_text?: string | null;
  duration_ms: number;
  char_count: number;
  line_count: number;
  chars_per_second: number;
  ocr_confidence?: number | null;
  asr_confidence?: number | null;
  issues: SubtitleQualityIssue[];
}

export interface SubtitleDocumentQualityReport {
  document_id: string;
  video_id?: string | null;
  project_id?: string | null;
  average_score: number;
  total_lines: number;
  needs_review_count: number;
  critical_count: number;
  warning_count: number;
  lines: SubtitleLineQualityScore[];
  summary_warnings: string[];
  issues_breakdown: Record<string, number>;
  report_file?: string | null;
  created_at: string;
}

export interface SubtitleQualityFlaggedLinesResponse {
  items: SubtitleLineQualityScore[];
}

export interface SubtitleRewriteSuggestionResponse {
  suggestion: string;
  source: string;
  issues: Array<Record<string, unknown>>;
}

export type SubtitleRewriteStyle = 'short_natural' | 'very_short' | 'casual_tiktok' | 'clear_review' | 'sales_natural';

export interface SubtitleRewriteSuggestion {
  id: string;
  document_id: string;
  line_index: number;
  source_text?: string | null;
  original_translation: string;
  suggested_text: string;
  style: SubtitleRewriteStyle;
  reason?: string | null;
  char_count_before: number;
  char_count_after: number;
  estimated_cps_before?: number | null;
  estimated_cps_after?: number | null;
  safety_warnings: string[];
  quality_score_before?: number | null;
  quality_score_after?: number | null;
  created_at: string;
  applied_at?: string | null;
  auto_applied: boolean;
}

export interface GenerateSubtitleRewriteRequest {
  style: SubtitleRewriteStyle;
  suggestion_count: number;
  max_chars?: number | null;
  preserve_keywords: string[];
  use_ai: boolean;
}

export interface SubtitleRewriteSuggestionsResponse {
  success: boolean;
  items: SubtitleRewriteSuggestion[];
}

export interface ApplySubtitleRewriteResponse {
  success: boolean;
  line: SubtitleReviewLine;
}

export interface BulkRewriteFlaggedLinesRequest {
  style: SubtitleRewriteStyle;
  max_lines: number;
  only_issue_types: string[];
  auto_apply_safe_suggestions: boolean;
}

export interface BulkSubtitleRewriteResponse {
  success: boolean;
  processed_lines: number;
  suggestions_created: number;
  auto_applied: number;
  items: SubtitleRewriteSuggestion[];
}

export interface SubtitleReviewLine {
  index: number;
  start_ms: number;
  end_ms: number;
  source_text?: string | null;
  translated_text: string;
  edited_text?: string | null;
  status: SubtitleReviewStatus;
  warnings: string[];
  user_note?: string | null;
  quality_score?: number | null;
  quality_needs_review: boolean;
  quality_severity?: SubtitleQualitySeverity | null;
  quality_issues: SubtitleQualityIssue[];
  rewrite_history: Array<Record<string, unknown>>;
}

export interface SubtitleReviewDocument {
  id: string;
  project_id?: string | null;
  job_id?: string | null;
  video_id: string;
  video_path: string;
  source_language: string;
  target_language: string;
  source_type?: string | null;
  context: Record<string, unknown>;
  source_srt_path?: string | null;
  translated_srt_path: string;
  corrected_srt_path?: string | null;
  corrected_ass_path?: string | null;
  status: SubtitleReviewStatus;
  lines: SubtitleReviewLine[];
  line_count: number;
  reviewed_count: number;
  edited_count: number;
  warning_count: number;
  quality_average_score?: number | null;
  quality_needs_review_count: number;
  quality_critical_count: number;
  quality_warning_count: number;
  approval_quality_warning?: string | null;
  approval_quality_guard?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SubtitleReviewDocumentListResponse {
  items: SubtitleReviewDocument[];
}

export interface UpdateSubtitleLineRequest {
  edited_text?: string | null;
  status?: SubtitleReviewStatus | null;
  user_note?: string | null;
}

export interface SaveSubtitleReviewRequest {
  lines: SubtitleReviewLine[];
  mark_as_reviewed: boolean;
}

export interface ApproveSubtitleDocumentRequest {
  generate_ass: boolean;
  visual_style_preset_id?: string | null;
}

export interface RenderSubtitleReviewDocumentRequest {
  output_folder: string;
  settings: DouyinReupSettings;
}

export interface RenderApprovedSubtitleDocumentsRequest {
  job_id?: string | null;
  project_id?: string | null;
  output_folder: string;
  settings: DouyinReupSettings;
}

export interface SubtitleReviewRenderResponse {
  job_id: string;
  status: string;
}

export interface DouyinReupJobResultsResponse {
  summary?: DouyinReupSummary | null;
  outputs: DouyinOutputResult[];
}

export interface SilentReupDetectItem {
  video_path: string;
  has_speech: boolean;
  speech_score: number;
  recommended_mode: string;
  method?: string | null;
  warnings: string[];
}

export interface SilentReupDetectResponse {
  success: boolean;
  items: SilentReupDetectItem[];
}

export interface SilentReupPlanResponse {
  success: boolean;
  plan_id: string;
  plan: SilentReupPlan;
}

export interface SilentCaptionLine {
  index: number;
  start: number;
  end: number;
  text: string;
  source: string;
  segment_id?: string | null;
  template_id?: string | null;
  selected_industry?: string | null;
  selected_intent?: string | null;
  selection_reason?: string | null;
  quality_score?: number | null;
  quality_needs_review?: boolean;
  quality_issues?: string[];
  warnings: string[];
}

export type VisualTagCategory = 'industry' | 'scene' | 'action' | 'product_stage' | 'quality';

export interface SilentVisualTag {
  tag: string;
  category: VisualTagCategory;
  confidence: number;
  source: 'product_context' | 'ocr_text' | 'folder_name' | 'filename' | 'segment_type' | 'visual_rule' | 'user';
  reason?: string | null;
}

export interface SilentVisualSegment {
  id: string;
  video_path: string;
  start: number;
  end: number;
  duration: number;
  segment_type: string;
  visual_score: number;
  motion_score?: number | null;
  sharpness_score?: number | null;
  brightness_score?: number | null;
  representative_frame_path?: string | null;
  ocr_text?: string | null;
  visual_tags: SilentVisualTag[];
  primary_industry?: string | null;
  primary_scene?: string | null;
  primary_action?: string | null;
  visual_tag_confidence: number;
  warnings: string[];
}

export interface SegmentVisualTagResult {
  segment_id: string;
  video_path: string;
  start: number;
  end: number;
  tags: SilentVisualTag[];
  primary_industry?: string | null;
  primary_scene?: string | null;
  primary_action?: string | null;
  confidence: number;
  warnings: string[];
}

export interface VideoVisualTagReport {
  video_path: string;
  project_id?: string | null;
  job_id?: string | null;
  segment_results: SegmentVisualTagResult[];
  video_level_tags: SilentVisualTag[];
  recommended_industry?: string | null;
  recommended_strategy?: string | null;
  average_confidence: number;
  warnings: string[];
  created_at: string;
}

export interface SilentVisualTagVocabulary {
  industry: string[];
  scene: string[];
  action: string[];
  product_stage: string[];
  quality: string[];
}

export interface SilentReupPlan {
  video_path: string;
  strategy: string;
  has_speech: boolean;
  speech_score: number;
  visual_segments: SilentVisualSegment[];
  captions: SilentCaptionLine[];
  generate_voiceover: boolean;
  voiceover_script?: string | null;
  recommended_audio_mode: string;
  caption_generation: {
    industry: string;
    tone: string;
    strategy: string;
    template_count_available: number;
    captions_generated: number;
    regeneration_count: number;
    average_quality_score: number;
    warnings: string[];
  };
  visual_tagging: {
    enabled: boolean;
    recommended_industry: string;
    recommended_strategy: string;
    average_confidence: number;
    tag_sources: Record<string, number>;
    report_id?: string | null;
    warnings: string[];
  };
  visual_tag_report?: VideoVisualTagReport | null;
  warnings: string[];
}

export interface SilentCaptionTemplate {
  id: string;
  industry: string;
  intent: string;
  strategy: string;
  text: string;
  tone: string;
  max_chars: number;
  tags: string[];
}

export interface SilentCaptionTemplateListResponse {
  items: SilentCaptionTemplate[];
  total: number;
}

export interface SilentCaptionIndustriesResponse {
  items: Array<{ id: string; name: string }>;
}

export interface SilentReupReviewDocumentResponse {
  success: boolean;
  document_id: string;
}

export interface SilentVisualTagReportResponse {
  success: boolean;
  report: VideoVisualTagReport;
}

export interface SilentReupRenderResponse {
  success: boolean;
  job_id: string;
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

export type ProductImportInputType = 'manual' | 'text' | 'json' | 'txt' | 'csv' | 'shopee_extension';

export interface RawProductInput {
  input_type: ProductImportInputType;
  raw_text?: string | null;
  file_path?: string | null;
  file_content?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  structured_data?: Record<string, unknown> | null;
  save_to_inbox?: boolean;
  extractor_debug?: ShopeeExtractorDebugReport | null;
}

export type ExtractorDebugMethod =
  | 'json_ld'
  | 'meta'
  | 'dom_selector'
  | 'script_state'
  | 'visible_text'
  | 'fallback'
  | 'manual';

export interface ExtractorFieldDebug {
  field: string;
  valueFound: boolean;
  valuePreview?: string;
  method: ExtractorDebugMethod;
  confidence: number;
  warnings: string[];
}

export interface ShopeeExtractorDebugReport {
  url: string;
  extractedAt: string;
  pageType: 'product' | 'unknown' | 'unsupported';
  fields: ExtractorFieldDebug[];
  overallConfidence: number;
  warnings: string[];
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
  source?: {
    name?: string | null;
    url?: string | null;
  } | null;
  draft?: {
    id: string;
    title: string;
    status: string;
    confidence_score: number;
  } | null;
  import_inbox_url?: string | null;
  raw_preview?: string | null;
  error?: string | null;
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

export type ProductDraftStatus = 'new' | 'reviewed' | 'applied' | 'archived';

export interface ProductDraftSource {
  source_name?: string | null;
  source_url?: string | null;
  imported_at: string;
  imported_by: string;
}

export interface ProductDraft {
  id: string;
  title: string;
  status: ProductDraftStatus;
  source: ProductDraftSource;
  raw_input?: Record<string, unknown> | null;
  raw_text?: string | null;
  structured_data?: Record<string, unknown> | null;
  extractor_debug?: ShopeeExtractorDebugReport | null;
  normalized_product?: ProductInfoNormalized | null;
  validation_issues: ProductValidationIssue[];
  industry_preset_id?: string | null;
  confidence_score: number;
  user_note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductDraftListResponse {
  items: ProductDraft[];
  total: number;
}

export interface ProductDraftUpdateRequest {
  normalized_product?: ProductInfoNormalized | null;
  status?: ProductDraftStatus | null;
  user_note?: string | null;
}

export interface ProjectListItem {
  id: string;
  project_name: string;
  created_at: string;
}

export interface ProjectListResponse {
  items: ProjectListItem[];
}

export interface CreateProjectFromDraftRequest {
  project_name: string;
  source_folder: string;
  output_folder: string;
  render: {
    output_count: number;
    duration: number;
  };
  attach_selected_assets?: boolean;
  selected_asset_ids?: string[] | null;
}

export interface ProductDraftApplyResponse {
  success: boolean;
  project_id: string;
  draft_id: string;
  project_product: ProductInfo;
  industry_preset_id?: string | null;
  updated_config?: ProjectConfig | null;
}

export interface CreateProjectFromDraftResponse {
  success: boolean;
  project_id: string;
  draft_id: string;
  updated_config?: ProjectConfig | null;
}

export type ProductAssetType = 'image' | 'video' | 'thumbnail' | 'unknown';
export type ProductAssetRole =
  | 'main_product'
  | 'reference'
  | 'poster'
  | 'thumbnail'
  | 'description'
  | 'variation'
  | 'unused';
export type ProductAssetStatus = 'pending' | 'downloaded' | 'failed' | 'skipped';

export interface ProductAsset {
  id: string;
  project_id?: string | null;
  draft_id?: string | null;
  source_name?: string | null;
  source_url?: string | null;
  original_url?: string | null;
  asset_type: ProductAssetType;
  role: ProductAssetRole;
  status: ProductAssetStatus;
  filename?: string | null;
  local_path?: string | null;
  width?: number | null;
  height?: number | null;
  file_size?: number | null;
  mime_type?: string | null;
  quality_score?: number | null;
  is_selected: boolean;
  user_note?: string | null;
  warnings: string[];
  errors: string[];
  created_at: string;
  updated_at: string;
}

export interface ProductAssetListResponse {
  items: ProductAsset[];
}

export interface ProductAssetsImportResponse {
  success: boolean;
  items: ProductAsset[];
}

export interface AttachDraftAssetsResponse {
  success: boolean;
  project_id: string;
  attached_count: number;
  items: ProductAsset[];
}

export interface ProductReferenceAsset {
  asset_id: string;
  role: string;
  local_path?: string | null;
  original_url?: string | null;
  width?: number | null;
  height?: number | null;
  quality_score?: number | null;
  user_note?: string | null;
}

export interface ProductReferenceSummary {
  project_id: string;
  product_name: string;
  brand?: string | null;
  industry_preset_id?: string | null;
  visual_identity: string;
  product_accuracy_lock: string[];
  allowed_claims: string[];
  forbidden_claims: string[];
  reference_assets: ProductReferenceAsset[];
  main_product_asset_id?: string | null;
  warnings: string[];
}

export interface StoryboardScene {
  scene_index: number;
  duration_seconds: number;
  scene_type: string;
  purpose: string;
  visual_description: string;
  camera_direction: string;
  product_accuracy_notes: string[];
  subtitle_suggestion?: string | null;
  voiceover_suggestion?: string | null;
}

export interface ProductStoryboard {
  project_id: string;
  title: string;
  total_duration_seconds: number;
  aspect_ratio: string;
  scenes: StoryboardScene[];
  negative_prompt: string[];
  reference_assets: ProductReferenceAsset[];
}

export interface VideoPromptPack {
  project_id: string;
  product_name: string;
  prompt_type: string;
  model_hint?: string | null;
  product_reference_summary: ProductReferenceSummary;
  storyboard: ProductStoryboard;
  video_prompt: string;
  negative_prompt: string;
  short_prompt?: string | null;
  json_prompt?: Record<string, unknown> | null;
  created_at: string;
}

export interface ReferenceSummaryResponse {
  success: boolean;
  summary: ProductReferenceSummary;
}

export interface StoryboardRequest {
  duration_seconds: number;
  scene_count: number;
  style?: string | null;
}

export interface StoryboardResponse {
  success: boolean;
  storyboard: ProductStoryboard;
}

export interface VideoPromptPackRequest {
  duration_seconds: number;
  scene_count: number;
  model_hint?: string | null;
  style?: string | null;
}

export interface VideoPromptPackResponse {
  success: boolean;
  prompt_pack: VideoPromptPack;
  files: Record<string, string>;
}
