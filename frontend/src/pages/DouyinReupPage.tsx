import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  applyDouyinReupPreset,
  buildSilentReupPlan,
  createSilentReupReviewDocument,
  createDouyinExportPack,
  finalOutputQAReportUrl,
  getDouyinExportPack,
  getDouyinReupJobResults,
  getJobStatus,
  getSilentVisualTagVocabulary,
  getVisualStyles,
  listSilentCaptionIndustries,
  openDouyinExportPack,
  recommendDouyinReupPreset,
  regenerateSilentReupCaptions,
  updateSilentSegmentVisualTags,
  renderApprovedSubtitleReviewDocuments,
  retryDouyinReupJobWithPreset,
  retryFailedDouyinReupJob,
  runFinalOutputQAForJob,
  startDouyinReupProcess,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import SliderInput from '../components/SliderInput';
import GlassButton from '../components/glass/GlassButton';
import GlassCard from '../components/glass/GlassCard';
import GlassModal from '../components/glass/GlassModal';
import JobProgressPanel from '../components/jobs/JobProgressPanel';
import SegmentTagEditor from '../components/silent/SegmentTagEditor';
import SilentPlanPreview from '../components/silent/SilentPlanPreview';
import MusicFolderCard from '../components/start-workflow/MusicFolderCard';
import OutputFolderCard from '../components/start-workflow/OutputFolderCard';
import ProductContextCard from '../components/start-workflow/ProductContextCard';
import SourceFolderCard from '../components/start-workflow/SourceFolderCard';
import StartAdvancedSettingsDrawer from '../components/start-workflow/StartAdvancedSettingsDrawer';
import StartBatchButton from '../components/start-workflow/StartBatchButton';
import StartChecklistCard from '../components/start-workflow/StartChecklistCard';
import StartPresetSelector from '../components/start-workflow/StartPresetSelector';
import StartValidationAlert from '../components/start-workflow/StartValidationAlert';
import StartWorkflowLayout from '../components/start-workflow/StartWorkflowLayout';
import WorkflowHero from '../components/start-workflow/WorkflowHero';
import WorkflowPreviewPanel from '../components/start-workflow/WorkflowPreviewPanel';
import WorkflowStepper from '../components/workflow/WorkflowStepper';
import {
  browseStartFolder,
  getHealth,
  getPresets,
  scanDouyinFolder,
  startDouyinOneClick,
  startSilentOneClick,
} from '../services/startWorkflowApi';
import {
  addRecentMusicFolder,
  addRecentOutputFolder,
  addRecentSourceFolder,
  getLocalAppConfig,
  getRecentPaths,
  type LocalRecentPaths,
} from '../services/localAppApi';
import type {
  DouyinOutputResult,
  DouyinPresetRecommendationResponse,
  DouyinReupPreset,
  DouyinReupSummary,
  DouyinReupSettings,
  DouyinVideoItem,
  JobStatus,
  PlatformExportPack,
  PlatformTarget,
  SystemDependencyStatusResponse,
  SilentReupPlanResponse,
  SilentVisualTagVocabulary,
  VisualStylePreset,
} from '../types/project';
import type {
  JobStartedView,
  StartChecklistItem,
  StartPresetViewModel,
  StartRecentFolder,
  StartScanSummary,
  StartValidationMessage,
  StartWorkflowMode,
} from '../types/startWorkflow';
import { summarizeStartScan } from '../types/startWorkflow';

type ExportOptions = {
  copy_videos: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  include_captions: boolean;
  include_posting_checklist: boolean;
};

type SilentProductContext = {
  product_name: string;
  industry: string;
  features: string;
  cta: string;
};

const DEFAULT_SILENT_INDUSTRIES = [
  { id: 'general_product', name: 'General Product' },
  { id: 'home_goods', name: 'Home Goods' },
  { id: 'kitchen_goods', name: 'Kitchen Goods' },
  { id: 'storage_organization', name: 'Storage / Organization' },
  { id: 'desk_setup', name: 'Desk Setup' },
  { id: 'dorm_goods', name: 'Dorm Goods' },
  { id: 'beauty_goods', name: 'Beauty Goods' },
  { id: 'cleaning_goods', name: 'Cleaning Goods' },
];

const DEFAULT_VISUAL_TAG_VOCABULARY: SilentVisualTagVocabulary = {
  industry: DEFAULT_SILENT_INDUSTRIES.map((item) => item.id),
  scene: ['home_scene', 'kitchen_scene', 'bathroom_scene', 'bedroom_scene', 'desk_scene', 'dorm_scene', 'vanity_scene', 'storage_scene', 'cleaning_scene'],
  action: ['unboxing', 'opening_package', 'hands_operation', 'placing_product', 'assembling', 'testing', 'pouring', 'wiping', 'cleaning', 'organizing', 'folding', 'comparison', 'before_after', 'closeup', 'product_reveal', 'usage_demo', 'result_showcase'],
  product_stage: ['packaging', 'first_look', 'detail_closeup', 'demo_step', 'benefit_scene', 'final_result', 'cta_scene'],
  quality: ['clear_frame', 'dark_frame', 'high_motion', 'low_motion', 'stable_shot', 'blur_risk'],
};

const DEFAULT_SETTINGS: DouyinReupSettings = {
  enabled: true,
  preset_id: 'safe_review',
  preset_name: 'Safe Review',
  source_language: 'zh',
  target_language: 'vi',
  translation_style: 'sat_nghia_troi_chay',
  subtitle_position: 'bottom_overlay',
  translation_provider: 'gemini',
  subtitle_source_priority: ['sidecar_srt', 'embedded_subtitle', 'asr', 'ocr_hardsub'],
  use_sidecar_srt: true,
  use_embedded_subtitle: true,
  use_asr_if_no_subtitle: true,
  asr_provider: 'faster_whisper',
  asr_model_size: 'medium',
  asr_device: 'auto',
  asr_vad_filter: false,
  asr_subtitle_offset_seconds: -0.25,
  use_ocr_if_asr_failed: true,
  use_ocr_if_no_subtitle: true,
  ocr_provider: 'easyocr',
  ocr_language: 'ch',
  ocr_sample_fps: 2.0,
  ocr_region_mode: 'bottom_auto',
  ocr_manual_region: null,
  ocr_min_confidence: 0.55,
  ocr_dedupe_similarity: 0.86,
  ocr_min_text_length: 2,
  ocr_merge_gap_ms: 600,
  ocr_min_duration_ms: 500,
  ocr_max_duration_ms: 6000,
  prefer_ocr_over_asr_when_text_visible: false,
  visual_style_preset_id: 'clean_review_light',
  burn_subtitle: true,
  add_overlay: true,
  keep_original_audio: true,
  add_bgm: true,
  music_folder: '',
  bgm_volume: 0.16,
  original_audio_volume: 0.85,
  duck_bgm_when_voice: false,
  resolution: '1080x1920',
  fps: 30,
  process_mode: 'all',
  max_videos: null,
  selected_video_paths: [],
  source_selection_id: null,
  keep_temp: false,
  review_subtitles_before_render: true,
  auto_render_after_translation: false,
  auto_mark_low_quality_lines: true,
  enable_subtitle_rewrite_suggestions: true,
  auto_generate_rewrite_for_flagged_lines: false,
  auto_apply_safe_rewrites: false,
  default_rewrite_style: 'short_natural',
  enable_silent_immersive_mode: true,
  silent_mode_detection: true,
  silent_mode_strategy: 'chill_immersive',
  detect_speech_presence: true,
  speech_detection_threshold: 0.35,
  use_visual_segments_for_silent_video: true,
  silent_segment_duration_min: 1.2,
  silent_segment_duration_max: 4.0,
  generate_visual_captions: true,
  visual_caption_language: 'vi',
  visual_caption_style: 'natural_short',
  silent_caption_tone: 'natural',
  generate_voiceover_for_silent_video: false,
  silent_voiceover_provider: 'edge_tts',
  silent_voiceover_voice: 'vi-VN-HoaiMyNeural',
  keep_immersive_original_audio: true,
  immersive_original_audio_volume: 0.75,
  add_bgm_for_silent_video: true,
  immersive_bgm_volume: 0.18,
  silent_review_before_render: true,
};

const RECENT_SOURCE_KEY = 'auto-tool.recentSourceFolders';
const RECENT_OUTPUT_KEY = 'auto-tool.recentOutputFolders';
const RECENT_MUSIC_KEY = 'auto-tool.recentMusicFolders';
const LAST_PRESET_KEY = 'auto-tool.lastSelectedPreset';
const LAST_INDUSTRY_KEY = 'auto-tool.lastSelectedIndustry';
const LAST_TONE_KEY = 'auto-tool.lastSelectedTone';

function defaultProjectName(workflow: 'douyin' | 'silent'): string {
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '_');
  return workflow === 'silent' ? `silent_immersive_${date}` : `douyin_reup_${date}`;
}

function readRecentFolders(key: string): StartRecentFolder[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '[]') as string[];
    return parsed.filter(Boolean).slice(0, 5).map((path) => ({ id: path, path }));
  } catch {
    return [];
  }
}

function writeRecentFolders(key: string, folders: StartRecentFolder[]) {
  localStorage.setItem(key, JSON.stringify(folders.map((folder) => folder.path).slice(0, 5)));
}

function addRecentFolder(key: string, folders: StartRecentFolder[], path: string): StartRecentFolder[] {
  const trimmed = path.trim();
  if (!trimmed) return folders;
  const next = [{ id: trimmed, path: trimmed }, ...folders.filter((folder) => folder.path !== trimmed)].slice(0, 5);
  writeRecentFolders(key, next);
  return next;
}

function removeRecentFolder(key: string, folders: StartRecentFolder[], path: string): StartRecentFolder[] {
  const next = folders.filter((folder) => folder.path !== path);
  writeRecentFolders(key, next);
  return next;
}

function toRecentFolders(paths: string[]): StartRecentFolder[] {
  return paths.filter(Boolean).map((path) => ({ id: path, path }));
}

export default function DouyinReupPage({ initialWorkflow = 'douyin' }: { initialWorkflow?: 'douyin' | 'silent' }) {
  const navigate = useNavigate();
  const workflowMode: StartWorkflowMode = initialWorkflow === 'silent' ? 'silent_immersive' : 'douyin_voice';
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [riskyConfirmOpen, setRiskyConfirmOpen] = useState(false);
  const [projectName, setProjectName] = useState(() => defaultProjectName(initialWorkflow));
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState(() => localStorage.getItem('auto-tool.default-output-folder') || './examples/outputs');
  const [settings, setSettings] = useState<DouyinReupSettings>(() => ({
    ...DEFAULT_SETTINGS,
    music_folder: localStorage.getItem('auto-tool.default-bgm-folder') || DEFAULT_SETTINGS.music_folder,
    silent_caption_tone: localStorage.getItem(LAST_TONE_KEY) || DEFAULT_SETTINGS.silent_caption_tone,
  }));
  const [silentProductContext, setSilentProductContext] = useState<SilentProductContext>({
    product_name: '',
    industry: localStorage.getItem(LAST_INDUSTRY_KEY) || 'general_product',
    features: '',
    cta: '',
  });
  const [presets, setPresets] = useState<DouyinReupPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState(() => localStorage.getItem(LAST_PRESET_KEY) || (initialWorkflow === 'silent' ? 'silent_chill_immersive' : 'safe_review'));
  const [recommendation, setRecommendation] = useState<DouyinPresetRecommendationResponse | null>(null);
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [videos, setVideos] = useState<DouyinVideoItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [scanSummary, setScanSummary] = useState<StartScanSummary | null>(null);
  const [scanErrors, setScanErrors] = useState<string[]>([]);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [results, setResults] = useState<DouyinOutputResult[]>([]);
  const [summary, setSummary] = useState<DouyinReupSummary | null>(null);
  const [resultsTab, setResultsTab] = useState<'results' | 'final_qa'>('results');
  const [platformTarget, setPlatformTarget] = useState<PlatformTarget>('tiktok');
  const [exportPack, setExportPack] = useState<PlatformExportPack | null>(null);
  const [exportOutputIndexes, setExportOutputIndexes] = useState<number[]>([]);
  const [exportOptions, setExportOptions] = useState<ExportOptions>({
    copy_videos: true,
    include_subtitles: true,
    include_logs: true,
    include_captions: true,
    include_posting_checklist: true,
  });
  const [dependencyStatus, setDependencyStatus] = useState<SystemDependencyStatusResponse | null>(null);
  const [retryPresetByOutput, setRetryPresetByOutput] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [silentIndustries, setSilentIndustries] = useState<Array<{ id: string; name: string }>>([]);
  const [captionPreview, setCaptionPreview] = useState<SilentReupPlanResponse | null>(null);
  const [visualTagVocabulary, setVisualTagVocabulary] = useState<SilentVisualTagVocabulary>(DEFAULT_VISUAL_TAG_VOCABULARY);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [recentSourceFolders, setRecentSourceFolders] = useState(() => readRecentFolders(RECENT_SOURCE_KEY));
  const [recentOutputFolders, setRecentOutputFolders] = useState(() => readRecentFolders(RECENT_OUTPUT_KEY));
  const [recentMusicFolders, setRecentMusicFolders] = useState(() => readRecentFolders(RECENT_MUSIC_KEY));

  const done = jobStatus?.status === 'completed' || jobStatus?.status === 'completed_with_errors' || jobStatus?.status === 'failed';
  const canStart = sourceFolder.trim() && outputFolder.trim() && !busy && (!jobStatus || done);
  const selectedSet = useMemo(() => new Set(selectedPaths), [selectedPaths]);
  const reviewDocuments = useMemo(() => results.filter((output) => output.subtitle_review_document_id), [results]);
  const failedResults = useMemo(() => results.filter((output) => output.status === 'failed'), [results]);
  const qaFailedResults = useMemo(() => results.filter((output) => output.final_output_qa?.status === 'failed'), [results]);
  const resultGroups = useMemo(
    () => [
      { title: 'Ready for Review', items: results.filter((output) => output.status === 'needs_review') },
      { title: 'Rendered', items: results.filter((output) => output.status === 'success') },
      { title: 'Failed', items: results.filter((output) => output.status === 'failed') },
      {
        title: 'Skipped',
        items: results.filter((output) => !['needs_review', 'success', 'failed'].includes(output.status)),
      },
    ],
    [results],
  );
  const usesManualSubtitleReview = settings.review_subtitles_before_render && !settings.auto_render_after_translation;
  const isSilentPreset =
    selectedPresetId.startsWith('silent_') || Boolean(settings.enable_silent_immersive_mode && settings.preset_id?.startsWith('silent_'));
  const normalPresets = useMemo(() => presets.filter((preset) => !preset.id.startsWith('silent_')), [presets]);
  const silentPresets = useMemo(() => presets.filter((preset) => preset.id.startsWith('silent_')), [presets]);
  const selectedPreset = useMemo(() => presets.find((preset) => preset.id === selectedPresetId), [presets, selectedPresetId]);
  const recommendedPresetId = useMemo(
    () => pickRecommendedPresetId(workflowMode, sourceFolder, recommendation, presets),
    [workflowMode, sourceFolder, recommendation, presets],
  );
  const startPresetCards = useMemo(
    () => (workflowMode === 'silent_immersive' ? silentPresets : normalPresets).map((preset) => toStartPresetViewModel(preset, workflowMode, preset.id === recommendedPresetId)),
    [normalPresets, recommendedPresetId, silentPresets, workflowMode],
  );
  const selectedPresetCard = useMemo(
    () => startPresetCards.find((preset) => preset.id === selectedPresetId),
    [selectedPresetId, startPresetCards],
  );
  const recommendedPresetCard = useMemo(
    () => startPresetCards.find((preset) => preset.id === recommendedPresetId),
    [recommendedPresetId, startPresetCards],
  );
  const checklist = useMemo(
    () => buildChecklist({
      sourceFolder,
      outputFolder,
      selectedPreset: selectedPresetCard,
      scanSummary,
      scanErrors,
      musicFolder: settings.music_folder || '',
      backendReady: dependencyStatus !== null,
      autoRender: Boolean(selectedPresetCard?.autoRender),
    }),
    [dependencyStatus, outputFolder, scanErrors, scanSummary, selectedPresetCard, settings.music_folder, sourceFolder],
  );
  const validationMessages = useMemo(
    () => buildValidationMessages(checklist, selectedPresetCard, dependencyStatus, scanSummary),
    [checklist, dependencyStatus, scanSummary, selectedPresetCard],
  );
  const startDisabled = busy || checklist.some((item) => item.status === 'missing') || Boolean(jobStatus && !done);
  const riskyPreset = Boolean(selectedPresetCard?.autoRender && selectedPresetCard.id !== 'silent_chill_immersive');
  const jobStartedView: JobStartedView | null = jobId ? { jobId, projectName: projectName.trim() || defaultProjectName(initialWorkflow), jobStatus } : null;

  useEffect(() => {
    getLocalAppConfig()
      .then((config) => {
        if (!localStorage.getItem('auto-tool.default-output-folder')) setOutputFolder(config.default_output_folder);
        if (!localStorage.getItem('auto-tool.default-bgm-folder') && config.default_music_folder) {
          setSettings((current) => ({ ...current, music_folder: config.default_music_folder }));
        }
        setSourceFolder((current) => current || config.default_source_folder);
      })
      .catch(() => undefined);
    getRecentPaths()
      .then((recent) => {
        const hasBackendRecents = recent.source_folders.length || recent.output_folders.length || recent.music_folders.length;
        if (hasBackendRecents) applyBackendRecentPaths(recent);
      })
      .catch(() => undefined);
    getPresets()
      .then((loadedPresets) => {
        setPresets(loadedPresets);
        const savedPresetId = localStorage.getItem(LAST_PRESET_KEY);
        const savedPreset = savedPresetId
          ? loadedPresets.find((preset) => preset.id === savedPresetId && (initialWorkflow === 'silent' ? preset.id.startsWith('silent_') : !preset.id.startsWith('silent_')))
          : null;
        const defaultPreset = initialWorkflow === 'silent'
          ? loadedPresets.find((preset) => preset.id === 'silent_chill_immersive')
          : loadedPresets.find((preset) => preset.is_default) ?? loadedPresets[0];
        const selectedPreset = savedPreset ?? defaultPreset;
        if (selectedPreset) {
          setSelectedPresetId(selectedPreset.id);
          setSettings({
            ...selectedPreset.settings,
            music_folder: localStorage.getItem('auto-tool.default-bgm-folder') || DEFAULT_SETTINGS.music_folder,
            silent_caption_tone: localStorage.getItem(LAST_TONE_KEY) || selectedPreset.settings.silent_caption_tone,
          });
        }
      })
      .catch(() => setPresets([]));
    getVisualStyles()
      .then((response) => setVisualStyles(response.presets))
      .catch(() => setVisualStyles([]));
    getHealth()
      .then(setDependencyStatus)
      .catch(() => setDependencyStatus(null));
    listSilentCaptionIndustries()
      .then((response) => setSilentIndustries(response.items))
      .catch(() => setSilentIndustries(DEFAULT_SILENT_INDUSTRIES));
    getSilentVisualTagVocabulary()
      .then(setVisualTagVocabulary)
      .catch(() => setVisualTagVocabulary(DEFAULT_VISUAL_TAG_VOCABULARY));
  }, [initialWorkflow]);

  function applyBackendRecentPaths(recent: LocalRecentPaths) {
    const source = toRecentFolders(recent.source_folders);
    const output = toRecentFolders(recent.output_folders);
    const music = toRecentFolders(recent.music_folders);
    setRecentSourceFolders(source);
    setRecentOutputFolders(output);
    setRecentMusicFolders(music);
    writeRecentFolders(RECENT_SOURCE_KEY, source);
    writeRecentFolders(RECENT_OUTPUT_KEY, output);
    writeRecentFolders(RECENT_MUSIC_KEY, music);
  }

  function syncRecentPath(kind: 'source' | 'output' | 'music', path: string) {
    const action = kind === 'source'
      ? addRecentSourceFolder(path)
      : kind === 'output'
        ? addRecentOutputFolder(path)
        : addRecentMusicFolder(path);
    action.then(applyBackendRecentPaths).catch(() => undefined);
  }

  useEffect(() => {
    if (!jobId || done) return;
    const timer = window.setInterval(() => {
      getJobStatus(jobId)
        .then((status) => {
          setJobStatus(status);
          if (['completed', 'completed_with_errors', 'failed'].includes(status.status)) {
            void loadResults(jobId);
          }
        })
        .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải trạng thái job.'));
    }, 2000);
    return () => window.clearInterval(timer);
  }, [jobId, done]);

  async function handleScan() {
    setBusy(true);
    setError(null);
    setScanErrors([]);
    setResults([]);
    setSummary(null);
    try {
      const response = await scanDouyinFolder(sourceFolder);
      setVideos(response.media);
      setSelectedPaths([]);
      setScanSummary(summarizeStartScan(response.media, response.total_files, response.valid_videos, response.invalid_files));
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      syncRecentPath('source', sourceFolder);
      recommendDouyinReupPreset(sourceFolder)
        .then(setRecommendation)
        .catch(() => setRecommendation(null));
      if (response.errors.length) {
        setScanErrors(['Không thể scan folder này. Vui lòng kiểm tra đường dẫn hoặc quyền truy cập.', ...response.errors.slice(0, 2)]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể scan thư mục Douyin.');
      setScanErrors(['Không thể scan folder này. Vui lòng kiểm tra đường dẫn hoặc quyền truy cập.']);
    } finally {
      setBusy(false);
    }
  }

  async function handlePresetSelect(presetId: string) {
    setSelectedPresetId(presetId);
    localStorage.setItem(LAST_PRESET_KEY, presetId);
    setError(null);
    try {
      const response = await applyDouyinReupPreset({
        preset_id: presetId,
        current_settings: settings,
      });
      setSettings(response.settings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể áp dụng preset.');
    }
  }

  async function handleOneClickStart() {
    setBusy(true);
    setError(null);
    setResults([]);
    setSummary(null);
    try {
      const processMode: 'selected' | 'first_n' | 'all_videos' = selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all_videos';
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, outputFolder));
      syncRecentPath('source', sourceFolder);
      syncRecentPath('output', outputFolder);
      if (settings.music_folder?.trim()) {
        setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, settings.music_folder || ''));
        syncRecentPath('music', settings.music_folder || '');
      }
      const request = {
        project_name: projectName.trim() || 'douyin-reup',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        preset_id: selectedPresetId,
        bgm_folder: settings.music_folder?.trim() || null,
        visual_style_preset_id: settings.visual_style_preset_id,
        process_mode: processMode,
        max_videos: settings.max_videos,
        selected_video_paths: selectedPaths,
        review_subtitles_before_render: settings.review_subtitles_before_render,
        auto_render_after_translation: settings.auto_render_after_translation,
        product_context: buildSilentProductContext(silentProductContext),
        advanced_overrides: {
          ...(mode === 'advanced' ? settings : {}),
          silent_caption_tone: settings.silent_caption_tone,
        },
      };
      const response = initialWorkflow === 'silent' ? await startSilentOneClick(request) : await startDouyinOneClick(request);
      setJobId(response.job_id);
      setJobStatus({
        job_id: response.job_id,
        status: response.status,
        current_step: 'queued',
        progress: 0,
        total_outputs: response.total_outputs,
        completed_outputs: 0,
        failed_outputs: 0,
        logs: [],
      });
      setActionMessage('Batch đã bắt đầu. Bạn có thể xem tiến trình hoặc mở kết quả khi job hoàn tất.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu one-click batch.');
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    setBusy(true);
    setError(null);
    setResults([]);
    setSummary(null);
    try {
      const processSettings: DouyinReupSettings = {
        ...settings,
        enabled: true,
        music_folder: settings.music_folder?.trim() || null,
        process_mode: selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all',
        selected_video_paths: selectedPaths,
      };
      setRecentSourceFolders((current) => addRecentFolder(RECENT_SOURCE_KEY, current, sourceFolder));
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, outputFolder));
      syncRecentPath('source', sourceFolder);
      syncRecentPath('output', outputFolder);
      if (settings.music_folder?.trim()) {
        setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, settings.music_folder || ''));
        syncRecentPath('music', settings.music_folder || '');
      }
      const response = await startDouyinReupProcess({
        project_name: projectName.trim() || 'douyin-reup',
        source_folder: sourceFolder,
        output_folder: outputFolder,
        settings: processSettings,
      });
      setJobId(response.job_id);
      setJobStatus({
        job_id: response.job_id,
        status: response.status,
        current_step: 'queued',
        progress: 0,
        total_outputs: 0,
        completed_outputs: 0,
        failed_outputs: 0,
        logs: [],
      });
      setActionMessage('Batch đã bắt đầu. Bạn có thể xem tiến trình hoặc mở kết quả khi job hoàn tất.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu xử lý Douyin Reup.');
    } finally {
      setBusy(false);
    }
  }

  async function loadResults(targetJobId: string) {
    try {
      const response = await getDouyinReupJobResults(targetJobId);
      setResults(response.outputs);
      setSummary(response.summary ?? null);
      setExportOutputIndexes(response.outputs.filter((output) => Boolean(output.path)).map((output) => output.index));
      getDouyinExportPack(targetJobId)
        .then((packResponse) => setExportPack(packResponse.export_pack))
        .catch(() => setExportPack(null));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải kết quả Douyin Reup.');
    }
  }

  function toggleSelected(path: string) {
    setSelectedPaths((current) => (current.includes(path) ? current.filter((item) => item !== path) : [...current, path]));
  }

  function updateSettings(updates: Partial<DouyinReupSettings>) {
    if (typeof updates.silent_caption_tone === 'string') {
      localStorage.setItem(LAST_TONE_KEY, updates.silent_caption_tone);
    }
    setSettings((current) => ({ ...current, ...updates }));
  }

  function updateSilentProductContext(updates: Partial<SilentProductContext>) {
    if (typeof updates.industry === 'string') {
      localStorage.setItem(LAST_INDUSTRY_KEY, updates.industry);
    }
    setSilentProductContext((current) => ({ ...current, ...updates }));
  }

  async function browseSourceFolder() {
    const path = await browseStartFolder('Chọn folder video', sourceFolder);
    if (path) setSourceFolder(path);
  }

  async function browseOutputFolder() {
    const path = await browseStartFolder('Chọn output folder', outputFolder);
    if (path) {
      setOutputFolder(path);
      setRecentOutputFolders((current) => addRecentFolder(RECENT_OUTPUT_KEY, current, path));
      syncRecentPath('output', path);
    }
  }

  async function browseMusicFolder() {
    const path = await browseStartFolder('Chọn music folder', settings.music_folder || '');
    if (path) {
      updateSettings({ music_folder: path });
      setRecentMusicFolders((current) => addRecentFolder(RECENT_MUSIC_KEY, current, path));
      syncRecentPath('music', path);
    }
  }

  function requestStart() {
    if (riskyPreset) {
      setRiskyConfirmOpen(true);
      return;
    }
    void startCurrentWorkflow();
  }

  async function startCurrentWorkflow() {
    setRiskyConfirmOpen(false);
    await (mode === 'simple' ? handleOneClickStart() : handleStart());
  }

  async function handleGenerateCaptionPreview() {
    const videoPath = selectedPaths[0] || videos.find((video) => video.status === 'valid')?.path;
    if (!videoPath) {
      setError('Hãy scan thư mục và chọn ít nhất một video để tạo caption preview.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await buildSilentReupPlan({
        video_path: videoPath,
        settings: {
          ...settings,
          silent_caption_tone: settings.silent_caption_tone,
        },
        product_context: buildSilentProductContext(silentProductContext),
      });
      setCaptionPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo caption preview.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerateCaptionPreview() {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await regenerateSilentReupCaptions(captionPreview.plan_id, {
        industry: silentProductContext.industry,
        tone: settings.silent_caption_tone,
        strategy: settings.silent_mode_strategy,
        use_visual_tags: true,
        respect_user_tag_overrides: true,
      });
      setCaptionPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo lại captions.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveSegmentTags(segmentId: string, payload: {
    tags: string[];
    primary_industry: string | null;
    primary_scene: string | null;
    primary_action: string | null;
  }) {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await updateSilentSegmentVisualTags(captionPreview.plan_id, segmentId, payload);
      setCaptionPreview(response);
      setEditingSegmentId(null);
      setActionMessage(`Updated visual tags for ${segmentId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu visual tags.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateCaptionReviewDocument() {
    if (!captionPreview) return;
    setBusy(true);
    setError(null);
    try {
      const response = await createSilentReupReviewDocument(captionPreview.plan_id);
      navigate(`/subtitle-review/${response.document_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo review document.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRunFinalQA() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await runFinalOutputQAForJob(jobId, platformTarget);
      await loadResults(jobId);
      setResultsTab('final_qa');
      setActionMessage(`Checked ${response.summary.total_checked} final output(s).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not run final output QA.');
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateExportPack() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    setActionMessage(null);
    try {
      const response = await createDouyinExportPack(jobId, {
        platform_target: platformTarget,
        output_dir: null,
        ...exportOptions,
        output_indexes: exportOutputIndexes,
      });
      setExportPack(response.export_pack);
      await loadResults(jobId);
      setActionMessage(`Export pack created: ${response.export_pack.output_dir}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create export pack.');
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenExportPack() {
    if (!jobId) return;
    try {
      await openDouyinExportPack(jobId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open export pack folder.');
    }
  }

  function toggleExportOutput(index: number) {
    setExportOutputIndexes((current) => current.includes(index) ? current.filter((item) => item !== index) : [...current, index]);
  }

  function updateOcrManualRegion(key: 'x' | 'y' | 'width' | 'height', value: number) {
    setSettings((current) => ({
      ...current,
      ocr_manual_region: {
        x: current.ocr_manual_region?.x ?? 0,
        y: current.ocr_manual_region?.y ?? 1200,
        width: current.ocr_manual_region?.width ?? 1080,
        height: current.ocr_manual_region?.height ?? 500,
        [key]: value,
      },
    }));
  }

  async function handleRetryFailed() {
    if (!jobId || !failedResults.length) return;
    setBusy(true);
    setError(null);
    try {
      const response = await retryFailedDouyinReupJob(jobId, {
        retry_steps: ['asr', 'translation', 'render'],
        settings: settings.music_folder ? { music_folder: settings.music_folder } : {},
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể retry video lỗi.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryWithPreset(output?: DouyinOutputResult) {
    if (!jobId) return;
    const presetId = output ? retryPresetByOutput[output.index] || selectedPresetId : selectedPresetId;
    await handleRetryOutputWithPreset(output, presetId);
  }

  async function handleRetryOutputWithPreset(output: DouyinOutputResult | undefined, presetId: string) {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await retryDouyinReupJobWithPreset(jobId, {
        preset_id: presetId,
        video_ids: output ? [`video_${output.index.toString().padStart(3, '0')}`] : [],
        retry_steps: ['asr', 'translation', 'render'],
        settings,
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể retry bằng preset mới.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRenderApproved() {
    if (!jobId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await renderApprovedSubtitleReviewDocuments({
        job_id: jobId,
        output_folder: outputFolder,
        settings: { ...settings, review_subtitles_before_render: false, auto_render_after_translation: true },
      });
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể render subtitle đã approve.');
    } finally {
      setBusy(false);
    }
  }

  function updateAdvancedSettings(updates: Partial<DouyinReupSettings>) {
    setMode('advanced');
    updateSettings(updates);
  }

  function renderAdvancedSettings() {
    return (
      <>
        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">Subtitle</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Ngôn ngữ nguồn</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.source_language} onChange={(event) => updateAdvancedSettings({ source_language: event.target.value })} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Ngôn ngữ đích</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.target_language} onChange={(event) => updateAdvancedSettings({ target_language: event.target.value })} />
            </label>
            <Toggle label="Review subtitle trước render" checked={settings.review_subtitles_before_render} onChange={(value) => updateAdvancedSettings({ review_subtitles_before_render: value })} />
            <Toggle label="Render ngay sau khi dịch" checked={settings.auto_render_after_translation} onChange={(value) => updateAdvancedSettings({ auto_render_after_translation: value })} />
            <Toggle label="Burn subtitle vào video" checked={settings.burn_subtitle} onChange={(value) => updateAdvancedSettings({ burn_subtitle: value })} />
            <Toggle label="Dùng overlay" checked={settings.add_overlay} onChange={(value) => updateAdvancedSettings({ add_overlay: value })} />
          </div>
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">Nhận diện giọng nói</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label="Dịch thời gian sub" min={-1} max={1} step={0.05} value={settings.asr_subtitle_offset_seconds} onChange={(value) => updateAdvancedSettings({ asr_subtitle_offset_seconds: value })} />
            <Toggle label="Bật VAD cho giọng nói" checked={settings.asr_vad_filter} onChange={(value) => updateAdvancedSettings({ asr_vad_filter: value })} />
            <Toggle label="Dùng file .srt đi kèm" checked={settings.use_sidecar_srt} onChange={(value) => updateAdvancedSettings({ use_sidecar_srt: value })} />
            <Toggle label="Dùng subtitle nhúng" checked={settings.use_embedded_subtitle} onChange={(value) => updateAdvancedSettings({ use_embedded_subtitle: value })} />
            <Toggle label="Nhận diện giọng nói nếu thiếu subtitle" checked={settings.use_asr_if_no_subtitle} onChange={(value) => updateAdvancedSettings({ use_asr_if_no_subtitle: value })} />
          </div>
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold text-white">Nhận diện chữ trên màn hình</h3>
              <div className={dependencyStatus?.ocr_available ? 'mt-1 text-xs text-emerald-300' : 'mt-1 text-xs text-amber-300'}>{formatOcrDependencyStatus(dependencyStatus)}</div>
            </div>
            <Toggle label="Dùng OCR khi cần" checked={settings.use_ocr_if_no_subtitle || settings.use_ocr_if_asr_failed} onChange={(value) => updateAdvancedSettings({ use_ocr_if_no_subtitle: value, use_ocr_if_asr_failed: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">OCR provider</span>
              <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.ocr_provider} onChange={(event) => updateAdvancedSettings({ ocr_provider: event.target.value })}>
                <option value="paddleocr">PaddleOCR</option>
                <option value="easyocr">EasyOCR</option>
                <option value="mock_ocr">Mock OCR</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">OCR region</span>
              <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.ocr_region_mode} onChange={(event) => updateAdvancedSettings({ ocr_region_mode: event.target.value })}>
                <option value="bottom_auto">Bottom auto</option>
                <option value="middle_lower">Middle lower</option>
                <option value="full_frame">Full frame</option>
                <option value="manual">Manual</option>
              </select>
            </label>
            <SliderInput label="Sample FPS" min={0.5} max={5} step={0.5} value={settings.ocr_sample_fps} onChange={(value) => updateAdvancedSettings({ ocr_sample_fps: value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label="Min OCR confidence" min={0} max={1} step={0.05} value={settings.ocr_min_confidence} onChange={(value) => updateAdvancedSettings({ ocr_min_confidence: value })} />
            <Toggle label="Ưu tiên chữ trên màn hình" checked={settings.prefer_ocr_over_asr_when_text_visible} onChange={(value) => updateAdvancedSettings({ prefer_ocr_over_asr_when_text_visible: value })} />
          </div>
          {settings.ocr_region_mode === 'manual' ? (
            <div className="grid gap-2 sm:grid-cols-4">
              {(['x', 'y', 'width', 'height'] as const).map((key) => (
                <label className="block" key={key}>
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">{key}</span>
                  <input
                    className="h-10 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
                    type="number"
                    min={0}
                    value={settings.ocr_manual_region?.[key] ?? (key === 'width' ? 1080 : key === 'height' ? 500 : 0)}
                    onChange={(event) => updateOcrManualRegion(key, Number(event.target.value || 0))}
                  />
                </label>
              ))}
            </div>
          ) : null}
        </GlassCard>

        <GlassCard className="grid gap-4 p-4" strong>
          <h3 className="font-semibold text-white">Audio và Output</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput label="Âm lượng nhạc nền" min={0} max={1} step={0.01} value={settings.bgm_volume} onChange={(value) => updateAdvancedSettings({ bgm_volume: value })} />
            <SliderInput label="Âm lượng audio gốc" min={0} max={1} step={0.01} value={settings.original_audio_volume} onChange={(value) => updateAdvancedSettings({ original_audio_volume: value })} />
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Visual style</span>
              <select className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" value={settings.visual_style_preset_id} onChange={(event) => updateAdvancedSettings({ visual_style_preset_id: event.target.value })}>
                {visualStyles.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-200">Giới hạn số video</span>
              <input className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white" type="number" min={1} value={settings.max_videos ?? ''} onChange={(event) => updateAdvancedSettings({ max_videos: event.target.value ? Number(event.target.value) : null })} />
            </label>
          </div>
        </GlassCard>
      </>
    );
  }

  return (
    <>
      <StartWorkflowLayout
        hero={<WorkflowHero mode={workflowMode} onFocusStart={() => document.getElementById('start-source-folder')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} />}
        main={
          <>
            <div id="start-source-folder" />
            <ApiErrorBox error={error} />
            {actionMessage ? <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">{actionMessage}</div> : null}
            <WorkflowStepper steps={[
              { label: 'Nguồn', status: sourceFolder ? 'done' : 'active' },
              { label: 'Cấu hình', status: selectedPresetCard ? 'done' : 'pending' },
              { label: 'Đầu ra', status: outputFolder ? 'done' : 'pending' },
              { label: 'Kiểm tra', status: checklist.some((item) => item.status === 'missing') ? 'pending' : 'done' },
              { label: 'Bắt đầu', status: jobStatus && !done ? 'active' : done ? 'done' : 'pending' },
              { label: 'Xuất bản', status: exportPack ? 'done' : 'pending' },
            ]} />
            <SourceFolderCard
              mode={workflowMode}
              value={sourceFolder}
              busy={busy && !jobStatus}
              scanSummary={scanSummary}
              videos={videos}
              scanErrors={scanErrors}
              recentFolders={recentSourceFolders}
              onBrowse={() => void browseSourceFolder()}
              onChange={setSourceFolder}
              onScan={() => void handleScan()}
              onUseRecent={setSourceFolder}
              onRemoveRecent={(path) => setRecentSourceFolders((current) => removeRecentFolder(RECENT_SOURCE_KEY, current, path))}
            />
            <StartPresetSelector
              mode={workflowMode}
              presets={startPresetCards}
              selectedPresetId={selectedPresetId}
              recommendedPreset={recommendedPresetCard}
              recommendationReason={recommendation?.reason ?? recommendationReason(workflowMode, sourceFolder, recommendedPresetCard)}
              onSelect={(presetId) => void handlePresetSelect(presetId)}
            />
            <OutputFolderCard
              mode={workflowMode}
              outputFolder={outputFolder}
              projectName={projectName}
              recentFolders={recentOutputFolders}
              onBrowse={() => void browseOutputFolder()}
              onOutputFolderChange={setOutputFolder}
              onProjectNameChange={setProjectName}
              onUseRecent={setOutputFolder}
              onRemoveRecent={(path) => setRecentOutputFolders((current) => removeRecentFolder(RECENT_OUTPUT_KEY, current, path))}
            />
            <MusicFolderCard
              musicFolder={settings.music_folder || ''}
              addMusic={initialWorkflow === 'silent' ? settings.add_bgm_for_silent_video : settings.add_bgm}
              recentFolders={recentMusicFolders}
              onAddMusicChange={(value) => updateSettings(initialWorkflow === 'silent' ? { add_bgm_for_silent_video: value, add_bgm: value } : { add_bgm: value })}
              onBrowse={() => void browseMusicFolder()}
              onMusicFolderChange={(value) => updateSettings({ music_folder: value })}
              onUseRecent={(path) => updateSettings({ music_folder: path })}
              onRemoveRecent={(path) => setRecentMusicFolders((current) => removeRecentFolder(RECENT_MUSIC_KEY, current, path))}
            />
            {workflowMode === 'silent_immersive' ? (
              <ProductContextCard
                value={silentProductContext}
                industries={silentIndustries.length ? silentIndustries : DEFAULT_SILENT_INDUSTRIES}
                tone={settings.silent_caption_tone}
                busy={busy || videos.length === 0}
                hasPreview={Boolean(captionPreview)}
                onChange={updateSilentProductContext}
                onToneChange={(value) => updateSettings({ silent_caption_tone: value })}
                onPreview={() => void handleGenerateCaptionPreview()}
                onRegenerate={() => void handleRegenerateCaptionPreview()}
                onCreateReview={() => void handleCreateCaptionReviewDocument()}
              />
            ) : null}
            {captionPreview ? (
              <SilentPlanPreview
                preview={captionPreview}
                editingSegmentId={editingSegmentId}
                onEditSegment={setEditingSegmentId}
                onRegenerate={() => void handleRegenerateCaptionPreview()}
                disabled={busy}
                renderEditor={(segmentId) => {
                  const segment = captionPreview.plan.visual_segments.find((item) => item.id === segmentId);
                  return segment ? <SegmentTagEditor segment={segment} vocabulary={visualTagVocabulary} disabled={busy} onSave={(payload) => handleSaveSegmentTags(segment.id, payload)} onRegenerate={handleRegenerateCaptionPreview} /> : null;
                }}
              />
            ) : null}
          </>
        }
        side={
          <>
            <WorkflowPreviewPanel mode={workflowMode} preset={selectedPresetCard} scanSummary={scanSummary} jobStatus={jobStatus} />
            <StartChecklistCard items={checklist} />
            <StartValidationAlert messages={validationMessages} />
            <StartBatchButton
              disabled={startDisabled}
              loading={busy && !jobStatus}
              label={selectedPresetCard?.autoRender ? 'Bắt đầu xử lý nhanh' : 'Bắt đầu xử lý'}
              job={jobStartedView}
              onStart={requestStart}
            />
            <StartAdvancedSettingsDrawer
              open={advancedOpen}
              custom={mode === 'advanced'}
              onOpen={() => setAdvancedOpen(true)}
              onClose={() => setAdvancedOpen(false)}
              onReset={() => void handlePresetSelect(selectedPresetId)}
            >
              {renderAdvancedSettings()}
            </StartAdvancedSettingsDrawer>
          </>
        }
      />

      <GlassModal open={riskyConfirmOpen} title="Xác nhận preset xử lý nhanh" onClose={() => setRiskyConfirmOpen(false)}>
        <div className="grid gap-4 text-sm leading-6 text-slate-300">
          <p>Preset này sẽ xử lý nhanh và có thể bỏ qua bước review phụ đề. Bạn vẫn có thể kiểm tra video ở Results sau khi render.</p>
          <div className="flex flex-wrap gap-2">
            <GlassButton variant="primary" onClick={() => void startCurrentWorkflow()}>Tiếp tục</GlassButton>
            <GlassButton variant="secondary" onClick={() => { setRiskyConfirmOpen(false); void handlePresetSelect(initialWorkflow === 'silent' ? 'silent_chill_immersive' : 'safe_review'); }}>
              {initialWorkflow === 'silent' ? 'Đổi sang Chill Immersive' : 'Đổi sang Safe Review'}
            </GlassButton>
          </div>
        </div>
      </GlassModal>
      <section className="rounded-md border border-line bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">Video đã scan</h2>
          {scanSummary ? (
            <div className="text-sm text-muted">
              Tổng {scanSummary.total} file, hợp lệ {scanSummary.valid}, lỗi {scanSummary.invalid}
            </div>
          ) : null}
        </div>
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-line text-xs uppercase text-muted">
              <tr>
                <th className="py-2 pr-3">Chọn</th>
                <th className="py-2 pr-3">File</th>
                <th className="py-2 pr-3">Duration</th>
                <th className="py-2 pr-3">Subtitle</th>
                <th className="py-2 pr-3">Cảnh báo</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((video) => (
                <tr key={video.path} className="border-b border-line last:border-b-0">
                  <td className="py-3 pr-3">
                    <input
                      type="checkbox"
                      checked={selectedSet.has(video.path)}
                      onChange={() => toggleSelected(video.path)}
                    />
                  </td>
                  <td className="max-w-lg break-all py-3 pr-3">
                    <div className="font-medium text-ink">{video.filename}</div>
                    <div className="text-xs text-muted">{video.path}</div>
                  </td>
                  <td className="py-3 pr-3 text-muted">{video.duration.toFixed(1)}s</td>
                  <td className="py-3 pr-3 text-muted">
                    {video.sidecar_srt_path ? 'SRT đi kèm' : video.embedded_subtitle_found ? 'Nhúng' : 'Cần ASR'}
                  </td>
                  <td className="py-3 pr-3 text-muted">{video.warnings.join('; ') || '-'}</td>
                </tr>
              ))}
              {!videos.length ? (
                <tr>
                  <td className="py-6 text-sm text-muted" colSpan={5}>
                    Chưa scan video.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      {results.length ? (
        <section className="rounded-md border border-line bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button className={`px-3 py-2 text-sm font-semibold ${resultsTab === 'results' ? 'border-b-2 border-brand text-brand' : 'text-muted'}`} type="button" onClick={() => setResultsTab('results')}>
                Kết quả
              </button>
              <button className={`px-3 py-2 text-sm font-semibold ${resultsTab === 'final_qa' ? 'border-b-2 border-brand text-brand' : 'text-muted'}`} type="button" onClick={() => setResultsTab('final_qa')}>
                Đánh giá QA
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {failedResults.length ? (
                <button
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
                  type="button"
                  disabled={busy || !jobId}
                  onClick={() => void handleRetryFailed()}
                >
                  Thử lại các video lỗi
                </button>
              ) : null}
              {reviewDocuments.length > 0 && jobId ? (
                <>
                  <button
                    className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
                    type="button"
                    disabled={busy}
                    onClick={() => void handleRenderApproved()}
                  >
                    Render các file đã duyệt
                  </button>
                  <Link
                    className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                    to={`/subtitle-review?job_id=${encodeURIComponent(jobId)}`}
                  >
                    Mở Subtitle Review
                  </Link>
                </>
              ) : null}
            </div>
          </div>
          {resultsTab === 'results' && summary ? (
            <div className="mt-4 grid gap-2 text-sm sm:grid-cols-5">
              <Stat label="Cần duyệt" value={summary.needs_review ?? reviewDocuments.length} />
              <Stat label="Đã render" value={summary.rendered ?? results.filter((output) => output.status === 'success').length} />
              <Stat label="Lỗi" value={summary.failed ?? failedResults.length} />
              <Stat label="Im lặng" value={summary.silent_immersive?.videos_processed_silent ?? results.filter((output) => output.reup_mode === 'silent_immersive').length} />
              <Stat label="Chậm nhất" value={summary.performance?.slowest_step ?? '-'} />
            </div>
          ) : null}
          {resultsTab === 'results' ? <div className="mt-4 grid gap-5">
            {resultGroups.map((group) => group.items.length ? (
              <div key={group.title} className="grid gap-3">
                <div className="text-sm font-semibold text-ink">{group.title} ({group.items.length})</div>
                <div className="grid gap-4 lg:grid-cols-2">
            {group.items.map((output) => (
              <article key={output.index} className="rounded-md border border-line p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-ink">Video {output.index.toString().padStart(3, '0')}</div>
                  <span className={statusClass(output.status)}>
                    {output.status}
                  </span>
                </div>
                {output.path ? (
                  <video className="mt-3 aspect-[9/16] max-h-[520px] w-full rounded-md bg-black object-contain" src={videoFileUrl(output.path)} controls />
                ) : null}
                <div className="mt-3 grid gap-1 break-all text-xs text-muted">
                  <div>Output: {output.path || '-'}</div>
                  <div>Source type: {formatSourceType(output.subtitle_source)}</div>
                  <div>Source SRT: {output.source_srt_file || '-'}</div>
                  <div>Subtitle: {output.translated_srt_file || '-'}</div>
                  <div>Corrected SRT: {output.corrected_srt_file || '-'}</div>
                  <div>ASS: {output.corrected_ass_file || output.subtitle_ass_file || '-'}</div>
                  <div>Nhạc nền: {output.bgm_file || '-'}</div>
                  <div>Log: {output.log_file || '-'}</div>
                  <div>Failed step: {output.failed_step || '-'}</div>
                </div>
                {output.reup_mode === 'silent_immersive' ? (
                  <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
                    <div className="font-semibold">Mode: Silent Immersive</div>
                    <div>Strategy: {formatSilentStrategy(output.silent_strategy)}</div>
                    <div>Speech score: {Math.round((output.speech_score ?? 0) * 100)}%</div>
                    <div>Caption source: {formatCaptionSource(output.caption_source)}</div>
                    <div>Voiceover: {output.voiceover_file ? 'Có' : 'Không'}</div>
                    <div>BGM: {output.bgm_file ? 'Đã thêm' : 'Không'}</div>
                    <div className="break-all">Plan: {output.silent_plan_file || '-'}</div>
                    <div className="break-all">Voiceover script: {output.voiceover_script_file || '-'}</div>
                    <div className="break-all">Voiceover subtitle: {output.voiceover_subtitle_file || '-'}</div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {output.subtitle_review_document_id ? (
                        <button
                          className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                          type="button"
                          disabled={busy || !jobId}
                          onClick={() => void handleRenderApproved()}
                        >
                          Render các file đã duyệt
                        </button>
                      ) : null}
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'silent_product_voiceover')}
                      >
                        Thử lại với voiceover
                      </button>
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'voice_priority')}
                      >
                        Thử lại làm video ASR
                      </button>
                    </div>
                  </div>
                ) : null}
                {output.subtitle_source === 'ocr_hardsub' || output.ocr_debug_json_path ? (
                  <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    <div className="font-semibold">OCR Debug</div>
                    <div>OCR provider: {output.ocr_provider || settings.ocr_provider}</div>
                    <div>Region: {output.ocr_region_mode || settings.ocr_region_mode}</div>
                    <div>Frames sampled: {output.ocr_frame_count ?? 0}</div>
                    <div>Detected lines: {output.ocr_detected_line_count ?? 0}</div>
                    <div>Average confidence: {Math.round((output.ocr_average_confidence ?? 0) * 100)}%</div>
                    <div className="break-all">Debug JSON: {output.ocr_debug_json_path || '-'}</div>
                  </div>
                ) : null}
                {output.error_message ? <div className="mt-2 text-xs text-red-700">{output.error_message}</div> : null}
                {output.warnings.length ? <div className="mt-3 text-xs text-amber-700">{output.warnings.join('; ')}</div> : null}
                {output.errors.length ? <div className="mt-3 text-xs text-red-700">{output.errors.join('; ')}</div> : null}
                {output.status === 'failed' ? (
                  <div className="mt-3 flex flex-wrap items-end gap-2">
                    <label className="block">
                      <span className="mb-1 block text-xs font-semibold text-muted">Đổi Preset</span>
                      <select
                        className="h-9 rounded-md border border-line bg-white px-2 text-xs"
                        value={retryPresetByOutput[output.index] || selectedPresetId}
                        onChange={(event) =>
                          setRetryPresetByOutput((current) => ({ ...current, [output.index]: event.target.value }))
                        }
                      >
                        {presets.map((preset) => (
                          <option key={preset.id} value={preset.id}>
                            {preset.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      className="h-9 rounded-md border border-line px-3 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
                      type="button"
                      disabled={busy || !jobId}
                      onClick={() => void handleRetryWithPreset(output)}
                    >
                      Thử lại
                    </button>
                  </div>
                ) : null}
                {output.path ? (
                  <button
                    className="mt-3 rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(output.path)}
                  >
                    Sao chép đường dẫn
                  </button>
                ) : null}
                {output.subtitle_review_document_id ? (
                  <Link
                    className="ml-2 mt-3 inline-block rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                    to={`/subtitle-review/${output.subtitle_review_document_id}`}
                  >
                    {output.reup_mode === 'silent_immersive' ? 'Duyệt caption' : 'Duyệt phụ đề'}
                  </Link>
                ) : null}
              </article>
            ))}
                </div>
              </div>
            ) : null)}
          </div> : <FinalQAPanel
            busy={busy}
            jobId={jobId}
            outputs={results}
            summary={summary}
            platformTarget={platformTarget}
            setPlatformTarget={setPlatformTarget}
            selectedIndexes={exportOutputIndexes}
            toggleSelectedIndex={toggleExportOutput}
            onRunQA={handleRunFinalQA}
            onRetry={handleRetryWithPreset}
            exportOptions={exportOptions}
            setExportOptions={setExportOptions}
            onCreatePack={handleCreateExportPack}
            exportPack={exportPack}
            onOpenPack={handleOpenExportPack}
          />}
        </section>
      ) : null}
    </>
  );
}

function FinalQAPanel({
  busy,
  jobId,
  outputs,
  summary,
  platformTarget,
  setPlatformTarget,
  selectedIndexes,
  toggleSelectedIndex,
  onRunQA,
  onRetry,
  exportOptions,
  setExportOptions,
  onCreatePack,
  exportPack,
  onOpenPack,
}: {
  busy: boolean;
  jobId: string | null;
  outputs: DouyinOutputResult[];
  summary: DouyinReupSummary | null;
  platformTarget: PlatformTarget;
  setPlatformTarget: (value: PlatformTarget) => void;
  selectedIndexes: number[];
  toggleSelectedIndex: (index: number) => void;
  onRunQA: () => Promise<void>;
  onRetry: (output?: DouyinOutputResult) => Promise<void>;
  exportOptions: ExportOptions;
  setExportOptions: (updater: (current: ExportOptions) => ExportOptions) => void;
  onCreatePack: () => Promise<void>;
  exportPack: PlatformExportPack | null;
  onOpenPack: () => Promise<void>;
}) {
  const checkedOutputs = outputs.filter((output) => output.final_output_qa);
  const qaSummary = summary?.final_output_qa;
  const qaFailed = outputs.filter((output) => output.final_output_qa?.status === 'failed').length;
  const optionRows: Array<[keyof ExportOptions, string]> = [
    ['copy_videos', 'Bao gồm video'],
    ['include_subtitles', 'Bao gồm phụ đề'],
    ['include_logs', 'Bao gồm nhật ký'],
    ['include_captions', 'Bao gồm caption'],
    ['include_posting_checklist', 'Bao gồm checklist đăng bài'],
  ];
  return (
    <div className="mt-4 grid gap-5">
      <div className="grid gap-3 sm:grid-cols-5">
        <Stat label="Đã kiểm tra" value={qaSummary?.total_checked ?? checkedOutputs.length} />
        <Stat label="Đạt" value={qaSummary?.passed ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed').length} />
        <Stat label="Cảnh báo" value={qaSummary?.passed_with_warnings ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed_with_warnings').length} />
        <Stat label="Lỗi" value={qaSummary?.failed ?? qaFailed} />
        <Stat label="Trung bình" value={`${Math.round((qaSummary?.average_score ?? 0) * 100)}%`} />
      </div>
      <div className="flex flex-wrap items-end gap-3 border-y border-line py-4">
        <label>
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Nền tảng</span>
          <select className="h-10 rounded-md border border-line bg-white px-3 text-sm" value={platformTarget} onChange={(event) => setPlatformTarget(event.target.value as PlatformTarget)}>
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="generic_vertical">Generic Vertical</option>
          </select>
        </label>
        <button className="h-10 rounded-md border border-line px-4 text-sm font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRunQA()}>
          Chạy đánh giá QA
        </button>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {outputs.filter((output) => output.path).map((output) => {
          const qa = output.final_output_qa;
          return (
            <article className="rounded-md border border-line p-4" key={output.index}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-ink">{output.path.split(/[\\/]/).pop() || `Video ${output.index}`}</div>
                  <div className={qaStatusClass(qa?.status)}>QA: {formatQaStatus(qa?.status)}</div>
                </div>
                <label className="flex items-center gap-2 text-xs text-muted">
                  <input type="checkbox" checked={selectedIndexes.includes(output.index)} onChange={() => toggleSelectedIndex(output.index)} />
                  Xuất file
                </label>
              </div>
              <div className="mt-3 text-sm font-semibold text-ink">Điểm số: {qa ? `${Math.round(qa.score * 100)}%` : 'Chưa kiểm tra'}</div>
              {qa?.issues.length ? (
                <div className="mt-3 grid gap-2 text-xs">
                  {qa.issues.map((issue, index) => (
                    <div className={issue.severity === 'critical' ? 'text-red-700' : 'text-amber-700'} key={`${issue.issue_type}-${index}`}>
                      <div className="font-semibold">{issue.message}</div>
                      {issue.suggestion ? <div className="text-muted">{issue.suggestion}</div> : null}
                    </div>
                  ))}
                </div>
              ) : <div className="mt-3 text-xs text-green-700">Không có vấn đề kỹ thuật.</div>}
              <div className="mt-4 flex flex-wrap gap-2">
                {qa?.report_path ? <a className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand" href={finalOutputQAReportUrl(qa.report_path)} target="_blank" rel="noreferrer">Mở báo cáo QA</a> : null}
                {qa?.status === 'failed' ? <button className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRetry(output)}>Render lại</button> : null}
              </div>
            </article>
          );
        })}
      </div>
      <div className="grid gap-4 border-t border-line pt-5">
        <div>
          <h3 className="text-base font-semibold text-ink">Gói xuất tệp tin cho nền tảng</h3>
          <p className="mt-1 text-xs text-muted">Chuẩn bị các tệp tin cục bộ để kiểm tra và đăng tải.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {optionRows.map(([key, label]) => (
            <label className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm" key={key}>
              <input type="checkbox" checked={exportOptions[key]} onChange={(event) => setExportOptions((current) => ({ ...current, [key]: event.target.checked }))} />
              <span>{label}</span>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200" type="button" disabled={busy || !jobId || !selectedIndexes.length} onClick={() => void onCreatePack()}>
            Tạo gói xuất file
          </button>
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => void navigator.clipboard.writeText(exportPack.output_dir)}>Sao chép đường dẫn</button> : null}
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => void onOpenPack()}>Mở thư mục</button> : null}
        </div>
        {exportPack ? (
          <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            <div className="font-semibold">Đã tạo gói xuất file</div>
            <div className="break-all text-xs">{exportPack.output_dir}</div>
            <div className="mt-1 text-xs">{exportPack.items.filter((item) => item.exists).length} tệp tin sẵn sàng.</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function toStartPresetViewModel(
  preset: DouyinReupPreset,
  mode: StartWorkflowMode,
  recommended: boolean,
): StartPresetViewModel {
  return {
    id: preset.id,
    name: presetDisplayName(preset),
    description: shortPresetDescription(preset),
    badge: recommended ? undefined : presetBadge(preset),
    recommended,
    reviewRequired: Boolean(preset.settings.review_subtitles_before_render || preset.settings.silent_review_before_render),
    autoRender: Boolean(preset.settings.auto_render_after_translation || preset.id === 'fast_auto' || preset.id === 'silent_sales_recut'),
    mode,
  };
}

function presetDisplayName(preset: DouyinReupPreset): string {
  const names: Record<string, string> = {
    safe_review: 'Safe Review',
    fast_auto: 'Fast Auto',
    ocr_priority: 'OCR Priority',
    voice_priority: 'Voice Priority',
    clean_subtitle_only: 'Clean Subtitle Only',
    music_recut: 'Music Recut',
    silent_chill_immersive: 'Chill Immersive',
    silent_product_voiceover: 'Product Voiceover',
    silent_sales_recut: 'Sales Recut',
  };
  return names[preset.id] ?? preset.name;
}

function shortPresetDescription(preset: DouyinReupPreset): string {
  const descriptions: Record<string, string> = {
    safe_review: 'Dịch xong cho bạn kiểm tra trước khi render.',
    fast_auto: 'Tự dịch và render nhanh.',
    ocr_priority: 'Dành cho video có nhiều chữ Trung trên màn hình.',
    voice_priority: 'Dành cho video có lời thoại tiếng Trung rõ.',
    clean_subtitle_only: 'Chỉ tạo phụ đề sạch, ít hiệu ứng.',
    music_recut: 'Giữ sub, thêm nhạc nền nổi bật hơn.',
    silent_chill_immersive: 'Giữ vibe gốc, thêm caption Việt nhẹ.',
    silent_product_voiceover: 'Tạo voice review tiếng Việt từ cảnh quay.',
    silent_sales_recut: 'Caption ngắn, có hook và CTA.',
  };
  return descriptions[preset.id] ?? preset.description;
}

function presetBadge(preset: DouyinReupPreset): string {
  const badges: Record<string, string> = {
    safe_review: 'Khuyên dùng',
    fast_auto: 'Nhanh',
    ocr_priority: 'Chữ (OCR)',
    voice_priority: 'Giọng nói',
    clean_subtitle_only: 'Chỉ phụ đề',
    music_recut: 'Nhạc',
    silent_chill_immersive: 'Khuyên dùng',
    silent_product_voiceover: 'Giọng nói',
    silent_sales_recut: 'Bán hàng',
  };
  return badges[preset.id] ?? preset.ui_badge;
}

function pickRecommendedPresetId(
  mode: StartWorkflowMode,
  sourceFolder: string,
  recommendation: DouyinPresetRecommendationResponse | null,
  presets: DouyinReupPreset[],
): string {
  const presetIds = new Set(presets.map((preset) => preset.id));
  const lower = sourceFolder.toLowerCase();
  if (mode === 'silent_immersive') return presetIds.has('silent_chill_immersive') ? 'silent_chill_immersive' : presets.find((preset) => preset.id.startsWith('silent_'))?.id ?? '';
  if (recommendation?.preset_id && presetIds.has(recommendation.preset_id) && !recommendation.preset_id.startsWith('silent_')) return recommendation.preset_id;
  if (/(ocr|subtitle|sub|chinese|text|trung|zh)/i.test(lower) && presetIds.has('ocr_priority')) return 'ocr_priority';
  if (/(fast|quick|nhanh)/i.test(lower) && presetIds.has('fast_auto')) return 'fast_auto';
  return presetIds.has('safe_review') ? 'safe_review' : presets.find((preset) => !preset.id.startsWith('silent_'))?.id ?? '';
}

function recommendationReason(
  mode: StartWorkflowMode,
  sourceFolder: string,
  preset?: StartPresetViewModel,
): string {
  if (!preset) return '';
  if (mode === 'silent_immersive') return 'Silent Mode nên bắt đầu bằng preset nhẹ, giữ vibe gốc và cho bạn review caption.';
  if (preset.id === 'ocr_priority') return 'Tên folder có tín hiệu chữ/subtitle, nên ưu tiên nhận diện chữ trên màn hình.';
  if (preset.id === 'fast_auto') return 'Tên folder có tín hiệu cần xử lý nhanh, preset này bỏ qua bớt bước review.';
  if (sourceFolder.trim()) return 'An toàn hơn vì bạn có thể kiểm tra phụ đề trước khi render.';
  return 'Preset mặc định an toàn cho batch mới.';
}

function buildChecklist({
  sourceFolder,
  outputFolder,
  selectedPreset,
  scanSummary,
  scanErrors,
  musicFolder,
  backendReady,
  autoRender,
}: {
  sourceFolder: string;
  outputFolder: string;
  selectedPreset?: StartPresetViewModel;
  scanSummary: StartScanSummary | null;
  scanErrors: string[];
  musicFolder: string;
  backendReady: boolean;
  autoRender: boolean;
}): StartChecklistItem[] {
  return [
    {
      id: 'source',
      label: 'Folder video',
      status: sourceFolder.trim() ? (scanErrors.length ? 'missing' : scanSummary?.invalid ? 'warning' : 'ok') : 'missing',
      message: sourceFolder.trim()
        ? scanErrors.length
          ? scanErrors[0]
          : scanSummary
          ? `${scanSummary.valid} video hợp lệ${scanSummary.invalid ? `, ${scanSummary.invalid} file lỗi` : ''}.`
          : 'Có folder, hãy scan để kiểm tra nhanh.'
        : 'Chưa chọn folder video.',
    },
    {
      id: 'preset',
      label: 'Preset',
      status: selectedPreset ? (autoRender ? 'warning' : 'ok') : 'missing',
      message: selectedPreset ? selectedPreset.name : 'Chưa chọn preset.',
    },
    {
      id: 'output',
      label: 'Output folder',
      status: outputFolder.trim() ? 'ok' : 'missing',
      message: outputFolder.trim() ? 'Tool sẽ kiểm tra quyền ghi khi bắt đầu xử lý.' : 'Chưa chọn output folder.',
    },
    {
      id: 'music',
      label: 'Music',
      status: musicFolder.trim() ? 'ok' : 'warning',
      message: musicFolder.trim() ? 'Đã chọn music folder.' : 'Chưa chọn nhạc nền, tool vẫn có thể giữ âm thanh gốc.',
    },
    {
      id: 'backend',
      label: 'Backend',
      status: backendReady ? 'ok' : 'warning',
      message: backendReady ? 'Connected.' : 'Backend sẽ được kiểm tra lại khi start.',
    },
  ];
}

function buildValidationMessages(
  checklist: StartChecklistItem[],
  preset: StartPresetViewModel | undefined,
  dependencyStatus: SystemDependencyStatusResponse | null,
  scanSummary: StartScanSummary | null,
): StartValidationMessage[] {
  const messages: StartValidationMessage[] = [];
  checklist
    .filter((item) => item.status === 'missing')
    .forEach((item) => messages.push({ id: `missing-${item.id}`, tone: 'error', message: item.message || `${item.label} đang thiếu.` }));
  if (!dependencyStatus) messages.push({ id: 'backend', tone: 'warning', message: 'Backend đang offline hoặc chưa phản hồi. Hãy khởi động backend rồi thử lại.' });
  if (scanSummary?.invalid) messages.push({ id: 'scan-invalid', tone: 'warning', message: `Folder có ${scanSummary.invalid} file không đọc được. Tool sẽ bỏ qua hoặc bạn có thể kiểm tra lại.` });
  if (preset?.autoRender) messages.push({ id: 'auto-render', tone: 'warning', message: `${preset.name} có thể bỏ qua bước review phụ đề.` });
  if (preset?.id === 'ocr_priority' && dependencyStatus && !dependencyStatus.ocr_available) {
    messages.push({ id: 'ocr', tone: 'warning', message: 'OCR Priority cần OCR provider. Nếu OCR chưa sẵn sàng, tool có thể fallback hoặc báo lỗi.' });
  }
  return messages.slice(0, 4);
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function statusClass(status: string): string {
  if (status === 'success') return 'text-sm font-semibold text-green-700';
  if (status === 'needs_review') return 'text-sm font-semibold text-amber-700';
  return 'text-sm font-semibold text-red-700';
}

function qaStatusClass(status?: string): string {
  if (status === 'passed') return 'mt-1 text-xs font-semibold text-green-700';
  if (status === 'failed') return 'mt-1 text-xs font-semibold text-red-700';
  return 'mt-1 text-xs font-semibold text-amber-700';
}

function formatQaStatus(status?: string): string {
  if (!status) return 'Chưa kiểm tra';
  const labels: Record<string, string> = {
    passed: 'Đạt',
    failed: 'Thất bại',
    passed_with_warnings: 'Đạt (có cảnh báo)',
  };
  return labels[status] ?? status.replaceAll('_', ' ');
}

function formatSourceType(source?: string | null): string {
  const labels: Record<string, string> = {
    sidecar_srt: 'Sidecar SRT',
    embedded_subtitle: 'Embedded subtitle',
    asr: 'ASR',
    ocr_hardsub: 'OCR hard-sub',
    ocr_translation: 'OCR translated caption',
    visual_generated: 'Visual generated caption',
    template: 'Template caption',
    none: 'None',
  };
  return source ? labels[source] ?? source : '-';
}

function formatSilentStrategy(strategy?: string | null): string {
  const labels: Record<string, string> = {
    chill_immersive: 'Chill immersive',
    product_review_voiceover: 'Tạo voice review Việt',
    sales_recut: 'Recut bán hàng nhanh',
  };
  return strategy ? labels[strategy] ?? strategy : '-';
}

function formatCaptionSource(source?: string | null): string {
  const labels: Record<string, string> = {
    ocr_translation: 'OCR translated',
    visual_generated: 'Visual generated',
    template: 'Template',
    manual: 'Manual',
  };
  return source ? labels[source] ?? source : '-';
}

function buildSilentProductContext(context: SilentProductContext): Record<string, unknown> {
  return {
    product_name: context.product_name.trim(),
    category: context.industry,
    industry: context.industry,
    features: context.features
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean),
    cta: context.cta.trim(),
  };
}

function formatCaptionTime(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const remainder = safe % 60;
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

function formatVisualTag(value?: string | null): string {
  if (!value) return '-';
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTagSourceSummary(sources: Record<string, number>): string {
  const entries = Object.entries(sources).filter(([, count]) => count > 0);
  if (!entries.length) return 'No strong keyword source; visual rules were used.';
  return entries.map(([source, count]) => `${source.replaceAll('_', ' ')} (${count})`).join(', ');
}

function formatOcrDependencyStatus(status: SystemDependencyStatusResponse | null): string {
  if (!status) return 'OCR runtime: checking on startup';
  if (status.ocr_available) return `OCR runtime: ${status.ocr_provider || 'provider'} ready`;
  return status.ocr_message || 'OCR runtime: auto-installing in background';
}
