import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  applyDouyinReupPreset,
  createDouyinExportPack,
  finalOutputQAReportUrl,
  getDouyinExportPack,
  getDouyinReupJobResults,
  getJobStatus,
  getSystemDependencies,
  getVisualStyles,
  listDouyinReupPresets,
  openDouyinExportPack,
  recommendDouyinReupPreset,
  renderApprovedSubtitleReviewDocuments,
  retryDouyinReupJobWithPreset,
  retryFailedDouyinReupJob,
  runFinalOutputQAForJob,
  scanDouyinReupFolder,
  startDouyinOneClickBatch,
  startDouyinReupProcess,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import PathInput from '../components/PathInput';
import SliderInput from '../components/SliderInput';
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
  VisualStylePreset,
} from '../types/project';

type ExportOptions = {
  copy_videos: boolean;
  include_subtitles: boolean;
  include_logs: boolean;
  include_captions: boolean;
  include_posting_checklist: boolean;
};

type SilentProductContext = {
  product_name: string;
  category: string;
  features: string;
  cta: string;
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
  generate_voiceover_for_silent_video: false,
  silent_voiceover_provider: 'edge_tts',
  silent_voiceover_voice: 'vi-VN-HoaiMyNeural',
  keep_immersive_original_audio: true,
  immersive_original_audio_volume: 0.75,
  add_bgm_for_silent_video: true,
  immersive_bgm_volume: 0.18,
  silent_review_before_render: true,
};

export default function DouyinReupPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
  const [projectName, setProjectName] = useState('douyin-reup');
  const [sourceFolder, setSourceFolder] = useState('');
  const [outputFolder, setOutputFolder] = useState('./examples/outputs');
  const [settings, setSettings] = useState<DouyinReupSettings>(DEFAULT_SETTINGS);
  const [silentProductContext, setSilentProductContext] = useState<SilentProductContext>({
    product_name: '',
    category: '',
    features: '',
    cta: '',
  });
  const [presets, setPresets] = useState<DouyinReupPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState('safe_review');
  const [recommendation, setRecommendation] = useState<DouyinPresetRecommendationResponse | null>(null);
  const [visualStyles, setVisualStyles] = useState<VisualStylePreset[]>([]);
  const [videos, setVideos] = useState<DouyinVideoItem[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [scanSummary, setScanSummary] = useState<{ total: number; valid: number; invalid: number } | null>(null);
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

  useEffect(() => {
    listDouyinReupPresets()
      .then((response) => {
        setPresets(response.presets);
        const defaultPreset = response.presets.find((preset) => preset.is_default) ?? response.presets[0];
        if (defaultPreset) {
          setSelectedPresetId(defaultPreset.id);
          setSettings({ ...defaultPreset.settings, music_folder: DEFAULT_SETTINGS.music_folder });
        }
      })
      .catch(() => setPresets([]));
    getVisualStyles()
      .then((response) => setVisualStyles(response.presets))
      .catch(() => setVisualStyles([]));
    getSystemDependencies()
      .then(setDependencyStatus)
      .catch(() => setDependencyStatus(null));
  }, []);

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
    setResults([]);
    setSummary(null);
    try {
      const response = await scanDouyinReupFolder(sourceFolder);
      setVideos(response.media);
      setSelectedPaths([]);
      setScanSummary({
        total: response.total_files,
        valid: response.valid_videos,
        invalid: response.invalid_files,
      });
      recommendDouyinReupPreset(sourceFolder)
        .then(setRecommendation)
        .catch(() => setRecommendation(null));
      if (response.errors.length) {
        setError(response.errors.slice(0, 3).join('\n'));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể scan thư mục Douyin.');
    } finally {
      setBusy(false);
    }
  }

  async function handlePresetSelect(presetId: string) {
    setSelectedPresetId(presetId);
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
      const processMode = selectedPaths.length ? 'selected' : settings.max_videos ? 'first_n' : 'all_videos';
      const response = await startDouyinOneClickBatch({
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
        advanced_overrides: mode === 'advanced' ? { ...settings } : {},
      });
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
    setSettings((current) => ({ ...current, ...updates }));
  }

  function updateSilentProductContext(updates: Partial<SilentProductContext>) {
    setSilentProductContext((current) => ({ ...current, ...updates }));
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
        settings,
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

  function renderPresetCard(preset: DouyinReupPreset) {
    return (
      <button
        key={preset.id}
        className={`rounded-md border p-3 text-left transition ${
          selectedPresetId === preset.id ? 'border-brand bg-blue-50' : 'border-line bg-surface hover:border-brand'
        }`}
        type="button"
        onClick={() => void handlePresetSelect(preset.id)}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="font-semibold text-ink">{preset.name}</div>
          <span className="rounded bg-white px-2 py-0.5 text-xs font-semibold text-muted">{preset.ui_badge}</span>
        </div>
        <div className="mt-1 text-xs text-muted">{preset.description}</div>
        <div className="mt-2 flex flex-wrap gap-1 text-[11px] font-semibold text-muted">
          {preset.settings.review_subtitles_before_render ? <span className="rounded bg-white px-2 py-0.5">Review</span> : null}
          {preset.settings.prefer_ocr_over_asr_when_text_visible || preset.id === 'ocr_priority' ? <span className="rounded bg-white px-2 py-0.5">OCR</span> : null}
          {preset.settings.add_bgm || preset.settings.add_bgm_for_silent_video ? <span className="rounded bg-white px-2 py-0.5">BGM</span> : null}
          {preset.id.startsWith('silent_') ? <span className="rounded bg-white px-2 py-0.5">Silent</span> : null}
        </div>
      </button>
    );
  }

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Douyin Reup</h1>
          <p className="mt-1 text-sm text-muted">
            Xử lý video Douyin đã tải sẵn trong máy, dịch subtitle sang tiếng Việt và render lại với overlay/nhạc nền.
          </p>
        </div>
        {jobStatus ? (
          <div className="rounded-md border border-line bg-white px-4 py-3 text-sm">
            <div className="font-semibold text-ink">{jobStatus.progress}%</div>
            <div className="text-muted">{jobStatus.current_step}</div>
          </div>
        ) : null}
        <div className="flex rounded-md border border-line bg-white p-1 text-sm">
          <button
            className={`rounded px-3 py-1.5 font-semibold ${mode === 'simple' ? 'bg-brand text-white' : 'text-ink'}`}
            type="button"
            onClick={() => setMode('simple')}
          >
            Simple
          </button>
          <button
            className={`rounded px-3 py-1.5 font-semibold ${mode === 'advanced' ? 'bg-brand text-white' : 'text-ink'}`}
            type="button"
            onClick={() => setMode('advanced')}
          >
            Advanced
          </button>
        </div>
      </div>

      <ApiErrorBox error={error} />
      {actionMessage ? <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{actionMessage}</div> : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <section className="grid gap-4 rounded-md border border-line bg-white p-5">
          <h2 className="text-base font-semibold text-ink">Nguồn video</h2>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-ink">Tên project</span>
            <input
              className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
              lang="vi"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
            />
          </label>
          <PathInput label="Thư mục video Douyin" value={sourceFolder} onChange={setSourceFolder} required />
          <PathInput label="Thư mục output" value={outputFolder} onChange={setOutputFolder} required />
          <PathInput label="Thư mục nhạc nền" value={settings.music_folder || ''} onChange={(value) => updateSettings({ music_folder: value })} />

          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-ink">Preset</h3>
              {recommendation ? (
                <button
                  className="rounded-md border border-line px-3 py-1.5 text-xs font-semibold text-ink hover:border-brand"
                  type="button"
                  onClick={() => void handlePresetSelect(recommendation.preset_id)}
                >
                  Use recommended: {recommendation.preset_name}
                </button>
              ) : null}
            </div>
            <div className="grid gap-4">
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Douyin Reup thường</div>
                <div className="grid gap-3 md:grid-cols-2">{normalPresets.map(renderPresetCard)}</div>
              </div>
              {silentPresets.length ? (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Video không thoại / immersive</div>
                  <div className="grid gap-3 md:grid-cols-2">{silentPresets.map(renderPresetCard)}</div>
                </div>
              ) : null}
            </div>
            {recommendation ? (
              <div className="rounded-md border border-blue-100 bg-blue-50 p-3 text-xs text-blue-900">
                Recommended preset: <span className="font-semibold">{recommendation.preset_name}</span>. {recommendation.reason}
              </div>
            ) : null}
            {isSilentPreset ? (
              <div className="grid gap-3 rounded-md border border-emerald-100 bg-emerald-50 p-4">
                <div>
                  <h3 className="text-sm font-semibold text-ink">Video không thoại / immersive</h3>
                  <p className="mt-1 text-xs text-emerald-900">
                    Phù hợp với video chỉ có nhạc hoặc tiếng thao tác. Tool sẽ tạo caption tiếng Việt theo cảnh/OCR thay vì phụ thuộc ASR.
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">Tên sản phẩm</span>
                    <input
                      className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                      lang="vi"
                      value={silentProductContext.product_name}
                      onChange={(event) => updateSilentProductContext({ product_name: event.target.value })}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-ink">Ngành hàng</span>
                    <input
                      className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                      lang="vi"
                      value={silentProductContext.category}
                      onChange={(event) => updateSilentProductContext({ category: event.target.value })}
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">Điểm nổi bật</span>
                  <textarea
                    className="min-h-20 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
                    lang="vi"
                    value={silentProductContext.features}
                    onChange={(event) => updateSilentProductContext({ features: event.target.value })}
                    placeholder="Mỗi dòng là một điểm nổi bật"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-ink">CTA</span>
                  <input
                    className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                    lang="vi"
                    value={silentProductContext.cta}
                    onChange={(event) => updateSilentProductContext({ cta: event.target.value })}
                  />
                </label>
              </div>
            ) : null}
          </div>

          {mode === 'advanced' ? (
            <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Ngôn ngữ nguồn</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                value={settings.source_language}
                onChange={(event) => updateSettings({ source_language: event.target.value })}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Ngôn ngữ đích</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                value={settings.target_language}
                onChange={(event) => updateSettings({ target_language: event.target.value })}
              />
            </label>
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Visual style</span>
              <select
                className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                value={settings.visual_style_preset_id}
                onChange={(event) => updateSettings({ visual_style_preset_id: event.target.value })}
              >
                {visualStyles.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink">Giới hạn số video</span>
              <input
                className="h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                min={1}
                value={settings.max_videos ?? ''}
                onChange={(event) =>
                  updateSettings({ max_videos: event.target.value ? Number(event.target.value) : null })
                }
              />
            </label>
          </div>

          {mode === 'advanced' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput
              label="Âm lượng nhạc nền"
              min={0}
              max={1}
              step={0.01}
              value={settings.bgm_volume}
              onChange={(value) => updateSettings({ bgm_volume: value })}
            />
            <SliderInput
              label="Âm lượng audio gốc"
              min={0}
              max={1}
              step={0.01}
              value={settings.original_audio_volume}
              onChange={(value) => updateSettings({ original_audio_volume: value })}
            />
          </div>
          ) : null}

          {mode === 'advanced' ? (
            <>
          <div className="grid gap-3 sm:grid-cols-2">
            <SliderInput
              label="Dịch thời gian sub ASR"
              min={-1}
              max={1}
              step={0.05}
              value={settings.asr_subtitle_offset_seconds}
              onChange={(value) => updateSettings({ asr_subtitle_offset_seconds: value })}
            />
            <Toggle
              label="Bật VAD cho ASR"
              checked={settings.asr_vad_filter}
              onChange={(value) => updateSettings({ asr_vad_filter: value })}
            />
          </div>

          <div className="grid gap-3 rounded-md border border-line bg-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-ink">OCR hard subtitle</h3>
                <div className={dependencyStatus?.ocr_available ? 'text-xs text-green-700' : 'text-xs text-amber-700'}>
                  {formatOcrDependencyStatus(dependencyStatus)}
                </div>
              </div>
              <Toggle
                label="Use OCR if no subtitle / ASR failed"
                checked={settings.use_ocr_if_no_subtitle || settings.use_ocr_if_asr_failed}
                onChange={(value) => updateSettings({ use_ocr_if_no_subtitle: value, use_ocr_if_asr_failed: value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">OCR provider</span>
                <select
                  className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                  value={settings.ocr_provider}
                  onChange={(event) => updateSettings({ ocr_provider: event.target.value })}
                >
                  <option value="paddleocr">PaddleOCR</option>
                  <option value="easyocr">EasyOCR</option>
                  <option value="mock_ocr">Mock OCR</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-ink">OCR region</span>
                <select
                  className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
                  value={settings.ocr_region_mode}
                  onChange={(event) => updateSettings({ ocr_region_mode: event.target.value })}
                >
                  <option value="bottom_auto">Bottom auto</option>
                  <option value="middle_lower">Middle lower</option>
                  <option value="full_frame">Full frame</option>
                  <option value="manual">Manual</option>
                </select>
              </label>
              <SliderInput
                label="Sample FPS"
                min={0.5}
                max={5}
                step={0.5}
                value={settings.ocr_sample_fps}
                onChange={(value) => updateSettings({ ocr_sample_fps: value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <SliderInput
                label="Min OCR confidence"
                min={0}
                max={1}
                step={0.05}
                value={settings.ocr_min_confidence}
                onChange={(value) => updateSettings({ ocr_min_confidence: value })}
              />
              <Toggle
                label="Prefer OCR over ASR"
                checked={settings.prefer_ocr_over_asr_when_text_visible}
                onChange={(value) => updateSettings({ prefer_ocr_over_asr_when_text_visible: value })}
              />
            </div>
            {settings.ocr_region_mode === 'manual' ? (
              <div className="grid gap-2 sm:grid-cols-4">
                {(['x', 'y', 'width', 'height'] as const).map((key) => (
                  <label className="block" key={key}>
                    <span className="mb-1 block text-xs font-semibold uppercase text-muted">{key}</span>
                    <input
                      className="h-10 w-full rounded-md border border-line px-3 text-sm"
                      type="number"
                      min={0}
                      value={settings.ocr_manual_region?.[key] ?? (key === 'width' ? 1080 : key === 'height' ? 500 : 0)}
                      onChange={(event) => updateOcrManualRegion(key, Number(event.target.value || 0))}
                    />
                  </label>
                ))}
              </div>
            ) : null}
          </div>

          <div className="grid gap-2 text-sm text-ink sm:grid-cols-2">
            <Toggle label="Dùng file .srt đi kèm" checked={settings.use_sidecar_srt} onChange={(value) => updateSettings({ use_sidecar_srt: value })} />
            <Toggle label="Dùng subtitle nhúng" checked={settings.use_embedded_subtitle} onChange={(value) => updateSettings({ use_embedded_subtitle: value })} />
            <Toggle label="ASR nếu không có subtitle" checked={settings.use_asr_if_no_subtitle} onChange={(value) => updateSettings({ use_asr_if_no_subtitle: value })} />
            <Toggle label="Review subtitle trước render" checked={settings.review_subtitles_before_render} onChange={(value) => updateSettings({ review_subtitles_before_render: value })} />
            <Toggle label="Render ngay sau khi dịch" checked={settings.auto_render_after_translation} onChange={(value) => updateSettings({ auto_render_after_translation: value })} />
            <Toggle label="Burn subtitle vào video" checked={settings.burn_subtitle} onChange={(value) => updateSettings({ burn_subtitle: value })} />
            <Toggle label="Dùng overlay" checked={settings.add_overlay} onChange={(value) => updateSettings({ add_overlay: value })} />
          </div>

            </>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
              type="button"
              disabled={!sourceFolder.trim() || busy}
              onClick={() => void handleScan()}
            >
              {busy ? 'Đang xử lý...' : 'Scan video'}
            </button>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-200"
              type="button"
              disabled={!canStart}
              onClick={() => void (mode === 'simple' ? handleOneClickStart() : handleStart())}
            >
              {mode === 'simple' ? 'Start One-click Batch' : usesManualSubtitleReview ? 'Dịch và mở review subtitle' : 'Bắt đầu Douyin Reup'}
            </button>
          </div>
        </section>

        <aside className="grid gap-4">
          <section className="rounded-md border border-line bg-white p-5">
            <h2 className="text-base font-semibold text-ink">Tiến trình</h2>
            {jobStatus ? (
              <div className="mt-4 grid gap-3">
                <div className="h-2 overflow-hidden rounded-full bg-surface">
                  <div className="h-full bg-brand" style={{ width: `${jobStatus.progress}%` }} />
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <Stat label="Hoàn thành" value={jobStatus.completed_outputs} />
                  <Stat label="Lỗi" value={jobStatus.failed_outputs} />
                  <Stat label="Tổng" value={jobStatus.total_outputs} />
                </div>
                <div className="max-h-64 overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
                  {jobStatus.logs.length ? (
                    jobStatus.logs.map((log, index) => (
                      <div key={`${log.created_at}-${index}`} className="border-b border-line py-2 last:border-b-0">
                        <span className="font-semibold text-ink">{log.level.toUpperCase()}</span> {log.message}
                      </div>
                    ))
                  ) : (
                    <div>Chưa có log.</div>
                  )}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">Chưa có job nào đang chạy.</p>
            )}
          </section>

          <section className="rounded-md border border-line bg-white p-5">
            <h2 className="text-base font-semibold text-ink">Config JSON</h2>
            <pre className="mt-3 max-h-[420px] overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
              {JSON.stringify({ project_name: projectName, source_folder: sourceFolder, output_folder: outputFolder, settings }, null, 2)}
            </pre>
          </section>
        </aside>
      </div>

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
                Results
              </button>
              <button className={`px-3 py-2 text-sm font-semibold ${resultsTab === 'final_qa' ? 'border-b-2 border-brand text-brand' : 'text-muted'}`} type="button" onClick={() => setResultsTab('final_qa')}>
                Final QA
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
                  Retry failed
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
                    Render approved
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
              <Stat label="Needs review" value={summary.needs_review ?? reviewDocuments.length} />
              <Stat label="Rendered" value={summary.rendered ?? results.filter((output) => output.status === 'success').length} />
              <Stat label="Failed" value={summary.failed ?? failedResults.length} />
              <Stat label="Silent" value={summary.silent_immersive?.videos_processed_silent ?? results.filter((output) => output.reup_mode === 'silent_immersive').length} />
              <Stat label="Slowest" value={summary.performance?.slowest_step ?? '-'} />
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
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'silent_product_voiceover')}
                      >
                        Retry with voiceover
                      </button>
                      <button
                        className="rounded-md border border-emerald-300 bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 disabled:text-muted"
                        type="button"
                        disabled={busy || !jobId}
                        onClick={() => void handleRetryOutputWithPreset(output, 'voice_priority')}
                      >
                        Retry as ASR video
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
                      <span className="mb-1 block text-xs font-semibold text-muted">Change Preset</span>
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
                      Retry
                    </button>
                  </div>
                ) : null}
                {output.path ? (
                  <button
                    className="mt-3 rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                    type="button"
                    onClick={() => void navigator.clipboard.writeText(output.path)}
                  >
                    Copy path
                  </button>
                ) : null}
                {output.subtitle_review_document_id ? (
                  <Link
                    className="ml-2 mt-3 inline-block rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                    to={`/subtitle-review/${output.subtitle_review_document_id}`}
                  >
                    Review subtitle
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
    </div>
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
    ['copy_videos', 'Include videos'],
    ['include_subtitles', 'Include subtitles'],
    ['include_logs', 'Include logs'],
    ['include_captions', 'Include captions'],
    ['include_posting_checklist', 'Include posting checklist'],
  ];
  return (
    <div className="mt-4 grid gap-5">
      <div className="grid gap-3 sm:grid-cols-5">
        <Stat label="Checked" value={qaSummary?.total_checked ?? checkedOutputs.length} />
        <Stat label="Passed" value={qaSummary?.passed ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed').length} />
        <Stat label="Warnings" value={qaSummary?.passed_with_warnings ?? checkedOutputs.filter((item) => item.final_output_qa?.status === 'passed_with_warnings').length} />
        <Stat label="Failed" value={qaSummary?.failed ?? qaFailed} />
        <Stat label="Average" value={`${Math.round((qaSummary?.average_score ?? 0) * 100)}%`} />
      </div>
      <div className="flex flex-wrap items-end gap-3 border-y border-line py-4">
        <label>
          <span className="mb-1 block text-xs font-semibold uppercase text-muted">Platform</span>
          <select className="h-10 rounded-md border border-line bg-white px-3 text-sm" value={platformTarget} onChange={(event) => setPlatformTarget(event.target.value as PlatformTarget)}>
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="generic_vertical">Generic Vertical</option>
          </select>
        </label>
        <button className="h-10 rounded-md border border-line px-4 text-sm font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRunQA()}>
          Run Final QA
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
                  Export
                </label>
              </div>
              <div className="mt-3 text-sm font-semibold text-ink">Score: {qa ? `${Math.round(qa.score * 100)}%` : 'Not checked'}</div>
              {qa?.issues.length ? (
                <div className="mt-3 grid gap-2 text-xs">
                  {qa.issues.map((issue, index) => (
                    <div className={issue.severity === 'critical' ? 'text-red-700' : 'text-amber-700'} key={`${issue.issue_type}-${index}`}>
                      <div className="font-semibold">{issue.message}</div>
                      {issue.suggestion ? <div className="text-muted">{issue.suggestion}</div> : null}
                    </div>
                  ))}
                </div>
              ) : <div className="mt-3 text-xs text-green-700">No technical QA issues.</div>}
              <div className="mt-4 flex flex-wrap gap-2">
                {qa?.report_path ? <a className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand" href={finalOutputQAReportUrl(qa.report_path)} target="_blank" rel="noreferrer">Open QA Report</a> : null}
                {qa?.status === 'failed' ? <button className="rounded-md border border-line px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={busy || !jobId} onClick={() => void onRetry(output)}>Retry Render</button> : null}
              </div>
            </article>
          );
        })}
      </div>
      <div className="grid gap-4 border-t border-line pt-5">
        <div>
          <h3 className="text-base font-semibold text-ink">Platform Export Pack</h3>
          <p className="mt-1 text-xs text-muted">Prepare local files for manual review and posting.</p>
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
            Create Export Pack
          </button>
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => void navigator.clipboard.writeText(exportPack.output_dir)}>Copy Path</button> : null}
          {exportPack ? <button className="rounded-md border border-line px-4 py-2 text-sm font-semibold text-ink" type="button" onClick={() => void onOpenPack()}>Open Folder</button> : null}
        </div>
        {exportPack ? (
          <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            <div className="font-semibold">Export pack created</div>
            <div className="break-all text-xs">{exportPack.output_dir}</div>
            <div className="mt-1 text-xs">{exportPack.items.filter((item) => item.exists).length} files available.</div>
          </div>
        ) : null}
      </div>
    </div>
  );
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
  if (!status) return 'Not checked';
  return status.replaceAll('_', ' ');
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
    category: context.category.trim(),
    features: context.features
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean),
    cta: context.cta.trim(),
  };
}

function formatOcrDependencyStatus(status: SystemDependencyStatusResponse | null): string {
  if (!status) return 'OCR runtime: checking on startup';
  if (status.ocr_available) return `OCR runtime: ${status.ocr_provider || 'provider'} ready`;
  return status.ocr_message || 'OCR runtime: auto-installing in background';
}
