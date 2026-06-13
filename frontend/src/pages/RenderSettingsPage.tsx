import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  analyzeCropSafety,
  analyzeProjectSegments,
  checkConfigRequirements,
  checkProjectSafety,
  clearProjectCache,
  createProject,
  generateScriptVariants,
  getGoogleCloudTTSVoices,
  getJobResults,
  getJobStatus,
  getLatestScript,
  getPresets,
  getProject,
  getProjectCacheSummary,
  listProjectAssets,
  getSourceMedia,
  getScriptVariantStyles,
  getTTSProviders,
  getTimelineTemplates,
  getVisualStyles,
  getIndustryPresets,
  saveProjectScript,
  scanProject,
  startRender,
  videoFileUrl,
  deleteProject,
  duplicateProject,
} from '../api/client';
import { Copy, Trash2 } from 'lucide-react';
import GlassButton from '../components/glass/GlassButton';
import GlassModal from '../components/glass/GlassModal';
import ApiErrorBox from '../components/ApiErrorBox';
import EffectSliders from '../components/EffectSliders';
import NumberInput from '../components/NumberInput';
import PathInput from '../components/PathInput';
import PresetSelector from '../components/PresetSelector';
import RenderProgress from '../components/RenderProgress';
import WarningBox from '../components/WarningBox';
import ScriptEditorForm from '../components/script/ScriptEditorForm';
import IndustryPresetSelector from '../components/industry/IndustryPresetSelector';
import VisualStyleSelector from '../components/visualStyle/VisualStyleSelector';
import {
  DEFAULT_CROP_SAFETY_SETTINGS,
  DEFAULT_CACHE_SETTINGS,
  DEFAULT_MUSIC_SETTINGS,
  DEFAULT_TTS_SETTINGS,
  DEFAULT_VISUAL_STYLE_SETTINGS,
} from '../config/defaults';
import {
  DURATION_OPTIONS,
  EDIT_STRENGTH_OPTIONS,
  OUTPUT_COUNT_OPTIONS,
  VIDEO_STYLE_OPTIONS,
  VOICE_OPTIONS,
  effectsMatch,
} from '../config/simplePresets';
import type {
  EffectSettings,
  ApplyIndustryPresetOptions,
  IndustryPreset,
  JobOutput,
  JobStatus,
  CacheSummary,
  Preset,
  ProductVideoScript,
  ProjectConfig,
  ProductAsset,
  CropSafetyAnalyzeResponse,
  ScanResponse,
  SafetyCheckResult,
  SegmentScoringSummary,
  SourceMediaSummary,
  ScriptVariantStyle,
  ScriptVariantSummary,
  TimelineTemplateSummary,
  TTSProviderInfo,
  TTSVoiceInfo,
  VisualStylePreset,
  VisualStyleSettings,
} from '../types/project';
import { applyIndustryPresetToConfig, DEFAULT_INDUSTRY_APPLY_OPTIONS } from '../utils/industryPresetApply';
import {
  defaultProjectConfig,
  formatJson,
  isProjectDirty,
  loadProjectConfig,
  maskSensitiveConfig,
  saveProjectConfig,
} from '../utils/projectState';

const DONE_STATUSES = new Set(['completed', 'completed_with_errors', 'failed']);
const DEFAULT_TEMPLATE_ID = 'ugc_reviewer_natural';
const FALLBACK_TTS_PROVIDERS: TTSProviderInfo[] = [
  { id: 'edge_tts', name: 'Edge TTS', requires_api_key: false, online: true, recommended: true },
  { id: 'google_cloud_tts', name: 'Google Cloud TTS', requires_api_key: true, online: true, recommended: true },
  { id: 'piper', name: 'Piper', requires_api_key: false, online: false, recommended: false },
  { id: 'gtts', name: 'gTTS', requires_api_key: false, online: true, recommended: false },
  { id: 'silent', name: 'Âm thanh im lặng', requires_api_key: false, online: false, recommended: false },
];

type SettingsMode = 'simple' | 'advanced';

export default function RenderSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [mode, setMode] = useState<SettingsMode>('simple');
  const [config, setConfig] = useState<ProjectConfig | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [timelineTemplates, setTimelineTemplates] = useState<TimelineTemplateSummary[]>([]);
  const [scriptVariantStyles, setScriptVariantStyles] = useState<ScriptVariantStyle[]>([]);
  const [scriptVariantSummary, setScriptVariantSummary] = useState<ScriptVariantSummary[]>([]);
  const [visualStylePresets, setVisualStylePresets] = useState<VisualStylePreset[]>([]);
  const [industryPresets, setIndustryPresets] = useState<IndustryPreset[]>([]);
  const [industryApplyOptions, setIndustryApplyOptions] = useState<ApplyIndustryPresetOptions>(
    DEFAULT_INDUSTRY_APPLY_OPTIONS,
  );
  const [ttsProviders, setTTSProviders] = useState<TTSProviderInfo[]>([]);
  const [googleVoices, setGoogleVoices] = useState<TTSVoiceInfo[]>([]);
  const [loadingGoogleVoices, setLoadingGoogleVoices] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('Balanced Recut');
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [segmentScoring, setSegmentScoring] = useState<SegmentScoringSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingProject, setDeletingProject] = useState(false);
  const [duplicatingProject, setDuplicatingProject] = useState(false);

  async function handleDeleteProject() {
    if (!projectId) return;
    setDeletingProject(true);
    setError(null);
    try {
      await deleteProject(projectId);
      setDeleteConfirmOpen(false);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xóa dự án.');
    } finally {
      setDeletingProject(false);
    }
  }

  async function handleDuplicateProject() {
    if (!projectId) return;
    setDuplicatingProject(true);
    setError(null);
    try {
      const res = await duplicateProject(projectId);
      if (res.success && res.project_id) {
        navigate(`/settings/${res.project_id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể nhân bản dự án.');
    } finally {
      setDuplicatingProject(false);
    }
  }
  const [previewJobId, setPreviewJobId] = useState<string | null>(null);
  const [previewProjectId, setPreviewProjectId] = useState<string | null>(null);
  const [previewJob, setPreviewJob] = useState<JobStatus | null>(null);
  const [previewOutput, setPreviewOutput] = useState<JobOutput | null>(null);
  const [script, setScript] = useState<ProductVideoScript | null>(null);
  const [scriptValid, setScriptValid] = useState(true);
  const [scriptErrors, setScriptErrors] = useState<string[]>([]);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [savingScript, setSavingScript] = useState(false);
  const [safetyResult, setSafetyResult] = useState<SafetyCheckResult | null>(null);
  const [checkingSafety, setCheckingSafety] = useState(false);
  const [cropSafety, setCropSafety] = useState<CropSafetyAnalyzeResponse | null>(null);
  const [cacheSummary, setCacheSummary] = useState<CacheSummary | null>(null);
  const [cacheBusy, setCacheBusy] = useState(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);
  const [sourceMediaSummary, setSourceMediaSummary] = useState<SourceMediaSummary | null>(null);
  const [productAssets, setProductAssets] = useState<ProductAsset[]>([]);

  useEffect(() => {
    if (!projectId) return;

    const localConfig = loadProjectConfig(projectId);
    if (localConfig) {
      setConfig(localConfig);
      setDirty(isProjectDirty(projectId));
    } else {
      getProject(projectId)
        .then((project) => {
          setConfig(project.config);
          saveProjectConfig(projectId, project.config, false);
          setDirty(false);
        })
        .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải dự án.'));
    }

    getPresets()
      .then(setPresets)
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải mẫu cài đặt.'));

    getTimelineTemplates()
      .then((response) => setTimelineTemplates(response.templates))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải mẫu dòng thời gian.'));

    getScriptVariantStyles()
      .then((response) => setScriptVariantStyles(response.styles))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải kiểu kịch bản.'));

    getTTSProviders()
      .then((response) => setTTSProviders(response.providers))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải nhà cung cấp giọng đọc.'));
    getVisualStyles()
      .then((response) => setVisualStylePresets(response.presets))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải style overlay/subtitle.'));
    getIndustryPresets()
      .then((response) => setIndustryPresets(response.presets))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải danh sách ngành hàng.'));
    void loadCacheSummary(projectId);
    void loadSourceMediaSummary(projectId);
    void loadProductAssets(projectId);
  }, [projectId]);

  useEffect(() => {
    if (!previewJobId || !previewProjectId) return;
    const activePreviewJobId = previewJobId;
    const activePreviewProjectId = previewProjectId;
    let mounted = true;
    let finished = false;

    async function loadPreviewStatus() {
      try {
        const nextJob = await getJobStatus(activePreviewJobId);
        if (!mounted) return;
        setPreviewJob(nextJob);
        setError(null);

        if (DONE_STATUSES.has(nextJob.status)) {
          finished = true;
          const result = await getJobResults(activePreviewJobId);
          if (!mounted) return;
          setPreviewOutput(result.outputs[0] ?? null);

          const latestScript = await getLatestScript(activePreviewProjectId);
          if (!mounted) return;
          if (latestScript.script) setEditableScript(latestScript.script);

          try {
            const cropSafetyResult = await analyzeCropSafety(activePreviewProjectId);
            if (!mounted) return;
            setCropSafety(cropSafetyResult);
          } catch (cropErr) {
            if (!mounted) return;
            setCropSafety({
              success: false,
              error: cropErr instanceof Error ? cropErr.message : 'Không thể đọc báo cáo Crop Safety.',
            });
          }
          void loadCacheSummary(activePreviewProjectId);
          setBusy(false);
        }
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Không thể tải trạng thái render thử.');
        setBusy(false);
      }
    }

    void loadPreviewStatus();
    const interval = window.setInterval(() => {
      if (!finished) void loadPreviewStatus();
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, [previewJobId, previewProjectId]);

  const previewJson = useMemo(
    () => formatJson(maskSensitiveConfig(config ?? defaultProjectConfig())),
    [config],
  );
  const availableTTSProviders = ttsProviders.length ? ttsProviders : FALLBACK_TTS_PROVIDERS;
  const safetyBlocked = Boolean(safetyResult?.errors_count);

  function setEditableScript(nextScript: ProductVideoScript) {
    setScript(nextScript);
    setScriptValid(true);
    setScriptErrors([]);
    setScriptError(null);
  }

  function updateConfig(nextConfig: ProjectConfig) {
    setConfig(nextConfig);
    setDirty(true);
    setSafetyResult(null);
    setCropSafety(null);
    if (projectId) saveProjectConfig(projectId, nextConfig, true);
  }

  async function loadCacheSummary(activeProjectId: string) {
    try {
      const summary = await getProjectCacheSummary(activeProjectId);
      setCacheSummary(summary);
      setCacheMessage(null);
    } catch {
      setCacheSummary(null);
    }
  }

  async function loadSourceMediaSummary(activeProjectId: string) {
    try {
      const response = await getSourceMedia(activeProjectId);
      setSourceMediaSummary(response.summary);
    } catch {
      setSourceMediaSummary(null);
    }
  }

  async function loadProductAssets(activeProjectId: string) {
    try {
      const response = await listProjectAssets(activeProjectId);
      setProductAssets(response.items);
    } catch {
      setProductAssets([]);
    }
  }

  async function handleClearCache() {
    setCacheBusy(true);
    setCacheMessage(null);
    setError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const response = await clearProjectCache(activeProjectId);
      setCacheMessage(response.message || 'Đã xoá cache dự án.');
      await loadCacheSummary(activeProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xoá cache dự án.');
    } finally {
      setCacheBusy(false);
    }
  }

  function updateCache(patch: Partial<NonNullable<ProjectConfig['cache']>>) {
    if (!config) return;
    updateConfig({
      ...config,
      cache: {
        ...(config.cache ?? DEFAULT_CACHE_SETTINGS),
        ...patch,
      },
    });
  }

  async function ensureCurrentProject(): Promise<string> {
    if (!projectId || !config) throw new Error('Dự án chưa sẵn sàng.');
    if (!dirty) return projectId;

    const response = await createProject(config);
    saveProjectConfig(response.project_id, config, false);
    setDirty(false);
    navigate(`/settings/${response.project_id}`, { replace: true });
    return response.project_id;
  }

  async function handleScan() {
    setBusy(true);
    setError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const result = await scanProject(activeProjectId);
      setScanResult(result);
      const scoring = await analyzeProjectSegments(activeProjectId);
      setSegmentScoring(scoring);
      await loadSourceMediaSummary(activeProjectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể quét video.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRunSafetyCheck(): Promise<SafetyCheckResult | null> {
    setCheckingSafety(true);
    setError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const result = await checkProjectSafety(activeProjectId);
      setSafetyResult(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể chạy Product Info QA.');
      return null;
    } finally {
      setCheckingSafety(false);
    }
  }

  async function handleRender(previewOnly: boolean) {
    setBusy(true);
    setError(null);
    setScriptError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const requirements = await checkConfigRequirements({
        project_id: activeProjectId,
        mode: 'product_render',
      });
      if (!requirements.ready) {
        throw new Error(requirements.issues.map(formatRequirementIssue).join('\n'));
      }
      const safety = await checkProjectSafety(activeProjectId);
      setSafetyResult(safety);
      if (safety.errors_count > 0) {
        throw new Error('Product Info QA có lỗi cần sửa trước khi render.');
      }
      const response = await startRender(activeProjectId, previewOnly);
      if (previewOnly) {
        setPreviewProjectId(activeProjectId);
        setPreviewJobId(response.job_id);
        setPreviewJob(null);
        setPreviewOutput(null);
        setScript(null);
        setCropSafety(null);
        return;
      }
      navigate(`/queue/${activeProjectId}/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu render.');
      setBusy(false);
    }
  }

  function formatRequirementIssue(issue: { message: string; action: string }) {
    return `${issue.message}${issue.action ? `\n${issue.action}` : ''}`;
  }

  async function handleGenerateScriptVariants() {
    if (!config) return;

    setBusy(true);
    setError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const response = await generateScriptVariants(
        activeProjectId,
        config.render.output_count,
        config.timeline?.template_id ?? DEFAULT_TEMPLATE_ID,
      );
      setScriptVariantSummary(response.variants);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo biến thể kịch bản.');
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveScript() {
    const activeProjectId = previewProjectId ?? projectId;
    if (!activeProjectId || !script) return;
    if (!scriptValid) {
      setScriptError(scriptErrors[0] ?? 'Kịch bản không hợp lệ.');
      return;
    }

    setSavingScript(true);
    setScriptError(null);
    try {
      const response = await saveProjectScript(activeProjectId, script);
      if (response.script) setEditableScript(response.script);
    } catch (err) {
      setScriptError(err instanceof Error ? err.message : 'Không thể lưu kịch bản.');
    } finally {
      setSavingScript(false);
    }
  }

  function handleModeChange(nextMode: SettingsMode) {
    if (!config) return;
    if (nextMode === 'simple' && !findEditStrength(config.effects)) {
      const shouldReset = window.confirm('Đặt lại mức độ chỉnh sửa về mẫu Vừa cho chế độ đơn giản?');
      if (shouldReset) {
        const balanced = EDIT_STRENGTH_OPTIONS.find((option) => option.id === 'balanced') ?? EDIT_STRENGTH_OPTIONS[1];
        updateConfig({ ...config, effects: balanced.effects });
      }
    }
    setMode(nextMode);
  }

  function handlePreset(preset: Preset) {
    if (!config) return;
    setSelectedPreset(preset.name);
    updateConfig({
      ...config,
      effects: preset.effects,
      timeline: {
        ...(config.timeline ?? { template_id: DEFAULT_TEMPLATE_ID }),
        template_id: preset.timeline_template_id ?? DEFAULT_TEMPLATE_ID,
      },
    });
  }

  function handleIndustryPreset(presetId: string) {
    if (!config) return;
    const preset = industryPresets.find((item) => item.id === presetId);
    if (!preset) return;
    updateConfig(applyIndustryPresetToConfig(config, preset, industryApplyOptions));
  }

  function handleTimelineTemplate(templateId: string) {
    if (!config) return;
    updateConfig({
      ...config,
      timeline: {
        ...(config.timeline ?? { template_id: DEFAULT_TEMPLATE_ID }),
        template_id: templateId,
      },
    });
  }

  function updateTTS(patch: Partial<NonNullable<ProjectConfig['tts']>>) {
    if (!config) return;
    const current = config.tts ?? DEFAULT_TTS_SETTINGS;
    updateConfig({
      ...config,
      tts: {
        ...current,
        ...patch,
      },
    });
  }

  function handleTTSProviderChange(provider: string) {
    if (provider === 'google_cloud_tts') {
      updateTTS({ provider, voice: 'vi-VN-Wavenet-A', language: 'vi-VN', output_format: 'mp3' });
      return;
    }
    if (provider === 'edge_tts') {
      updateTTS({ provider, voice: 'vi-VN-HoaiMyNeural', language: 'vi', output_format: 'mp3' });
      return;
    }
    updateTTS({ provider });
  }

  async function handleLoadGoogleVoices() {
    if (!config) return;
    setLoadingGoogleVoices(true);
    setError(null);
    try {
      const languageCode = googleLanguageCode(config.tts?.voice, config.tts?.language);
      const response = await getGoogleCloudTTSVoices({}, languageCode);
      setGoogleVoices(response.voices);
      if (response.voices.length && !response.voices.some((voice) => voice.name === config.tts?.voice)) {
        updateTTS({ voice: response.voices[0].name, language: response.voices[0].language_codes[0] ?? languageCode });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải danh sách giọng Google Cloud TTS.');
    } finally {
      setLoadingGoogleVoices(false);
    }
  }

  if (!config) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-6">
        <ApiErrorBox error={error} />
        <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
          Đang tải dự án...
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Cài đặt render</h1>
          <p className="mt-1 text-sm text-muted">{config.project_name}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <GlassButton
            variant="secondary"
            loading={duplicatingProject}
            onClick={() => void handleDuplicateProject()}
            className="min-h-9 px-3 text-xs"
          >
            <Copy size={13} className="mr-1" />
            Nhân bản
          </GlassButton>
          <GlassButton
            variant="danger"
            loading={deletingProject}
            onClick={() => setDeleteConfirmOpen(true)}
            className="min-h-9 px-3 text-xs bg-red-950/20 text-red-300 border-red-900/30 hover:bg-red-900/20"
          >
            <Trash2 size={13} className="mr-1" />
            Xóa
          </GlassButton>
          <ModeToggle mode={mode} onChange={handleModeChange} />
          <div className="rounded bg-white px-3 py-2 text-xs text-muted shadow-sm">
            {dirty ? 'Dự án có thay đổi chưa lưu' : 'Dự án đã đồng bộ'}
          </div>
        </div>

      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <section className="space-y-5">
          {mode === 'simple' ? (
            <SimpleSettingsPanel
              config={config}
              visualStylePresets={visualStylePresets}
              industryPresets={industryPresets}
              onChange={updateConfig}
            />
          ) : (
          <AdvancedSettingsPanel
              config={config}
              presets={presets}
              visualStylePresets={visualStylePresets}
              industryPresets={industryPresets}
              industryApplyOptions={industryApplyOptions}
              selectedPreset={selectedPreset}
              timelineTemplates={timelineTemplates}
              scriptVariantStyles={scriptVariantStyles}
              scriptVariantSummary={scriptVariantSummary}
              availableTTSProviders={availableTTSProviders}
              googleVoices={googleVoices}
              loadingGoogleVoices={loadingGoogleVoices}
              scanResult={scanResult}
              segmentScoring={segmentScoring}
              busy={busy}
              safetyBlocked={safetyBlocked}
              onPreset={handlePreset}
              onIndustryApplyOptionsChange={setIndustryApplyOptions}
              onIndustrySelect={(presetId) =>
                updateConfig({
                  ...config,
                  industry: { preset_id: presetId },
                })
              }
              onIndustryPreset={handleIndustryPreset}
              onTimelineTemplate={handleTimelineTemplate}
              onGenerateScriptVariants={handleGenerateScriptVariants}
              onTTSProviderChange={handleTTSProviderChange}
              onTTSChange={updateTTS}
              onLoadGoogleVoices={handleLoadGoogleVoices}
              onVisualStyleChange={(patch) =>
                updateConfig({
                  ...config,
                  visual_style: {
                    ...(config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS),
                    ...patch,
                  },
                })
              }
              onEffectsChange={(effects) => updateConfig({ ...config, effects })}
              onCropSafetyChange={(patch) =>
                updateConfig({
                  ...config,
                  crop_safety: { ...(config.crop_safety ?? DEFAULT_CROP_SAFETY_SETTINGS), ...patch },
                })
              }
              onRenderChange={(patch) =>
                updateConfig({ ...config, render: { ...config.render, ...patch } })
              }
              onMusicChange={(patch) =>
                updateConfig({ ...config, music: mergeMusicSettings(config.music, patch) })
              }
              onScan={handleScan}
              onBack={() => navigate('/')}
              onRenderPreview={() => handleRender(true)}
              onRenderFull={() => handleRender(false)}
            />
          )}

          <ProductSafetyBox
            result={safetyResult}
            checking={checkingSafety}
            onRun={() => void handleRunSafetyCheck()}
          />

          <SourceMediaSummaryBox
            summary={sourceMediaSummary}
            onManage={() => projectId && navigate(`/projects/${projectId}/source-media`)}
          />

          <ProductAssetsSummaryBox
            assets={productAssets}
            onManage={() => projectId && navigate(`/projects/${projectId}/assets`)}
            onPromptPack={() => projectId && navigate(`/projects/${projectId}/prompt-pack`)}
          />

          <CachePanel
            config={config}
            summary={cacheSummary}
            busy={cacheBusy}
            message={cacheMessage}
            onChange={updateCache}
            onRefresh={() => projectId && void loadCacheSummary(projectId)}
            onClear={() => void handleClearCache()}
          />

          <ApiErrorBox error={error} />

          {mode === 'simple' ? (
            <div className="flex flex-wrap items-center gap-3">
              <button
                className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
                type="button"
                disabled={busy}
                onClick={() => navigate('/')}
              >
                Quay lại
              </button>
              <button
                className="rounded-md bg-slate-700 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                type="button"
                disabled={busy || safetyBlocked}
                onClick={() => handleRender(true)}
              >
                Render thử
              </button>
              <button
                className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                type="button"
                disabled={busy || safetyBlocked}
                onClick={() => handleRender(false)}
              >
                Render toàn bộ
              </button>
            </div>
          ) : null}

          {previewJobId ? (
            <PreviewSection
              job={previewJob}
              output={previewOutput}
              script={script}
              cropSafety={cropSafety}
              targetDuration={config.render.duration}
              scriptError={scriptError}
              savingScript={savingScript}
              onScriptChange={setScript}
              onValidationChange={(valid, errors) => {
                setScriptValid(valid);
                setScriptErrors(errors);
              }}
              onSaveScript={handleSaveScript}
              onRenderFull={() => handleRender(false)}
              onRenderPreviewAgain={() => handleRender(true)}
              fullRenderDisabled={busy || savingScript || safetyBlocked}
            />
          ) : null}
        </section>

        <aside className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h2 className="mb-3 text-base font-semibold text-ink">Tóm tắt cấu hình</h2>
          {mode === 'simple' ? (
            <FriendlySummary
              config={config}
              providers={availableTTSProviders}
              templates={timelineTemplates}
              visualStylePresets={visualStylePresets}
              industryPresets={industryPresets}
            />
          ) : (
            <pre className="max-h-[780px] overflow-auto rounded-md bg-surface p-4 text-xs leading-relaxed text-ink">
              {previewJson}
            </pre>
          )}
        </aside>
      </div>

      <GlassModal
        open={deleteConfirmOpen}
        title="Xác nhận xóa dự án"
        onClose={() => setDeleteConfirmOpen(false)}
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-200">
            Bạn có chắc chắn muốn xóa dự án <strong>{config.project_name}</strong>?
          </p>
          <p className="text-xs text-rose-300">
            Hành động này sẽ xóa vĩnh viễn tất cả cấu hình, kịch bản, các video kết quả và lịch sử tiến trình chạy của dự án này.
          </p>
          <div className="flex justify-end gap-3 mt-4">
            <GlassButton variant="ghost" onClick={() => setDeleteConfirmOpen(false)}>
              Hủy bỏ
            </GlassButton>
            <GlassButton variant="danger" loading={deletingProject} onClick={() => void handleDeleteProject()}>
              Xác nhận xóa
            </GlassButton>
          </div>
        </div>
      </GlassModal>
    </main>
  );
}

function ModeToggle({ mode, onChange }: { mode: SettingsMode; onChange: (mode: SettingsMode) => void }) {
  return (
    <div className="flex rounded-md border border-line bg-white p-1 shadow-sm">
      {(['simple', 'advanced'] as SettingsMode[]).map((item) => (
        <button
          key={item}
          className={`rounded px-3 py-1.5 text-sm font-semibold ${
            mode === item ? 'bg-brand text-white' : 'text-muted hover:text-ink'
          }`}
          type="button"
          onClick={() => onChange(item)}
        >
          {item === 'simple' ? 'Đơn giản' : 'Nâng cao'}
        </button>
      ))}
    </div>
  );
}

function OverlayModeControls({
  settings,
  onChange,
}: {
  settings: VisualStyleSettings;
  onChange: (patch: Partial<VisualStyleSettings>) => void;
}) {
  const mode = settings.overlay_mode ?? DEFAULT_VISUAL_STYLE_SETTINGS.overlay_mode ?? 'preset';
  const customPath = settings.custom_overlay_path ?? DEFAULT_VISUAL_STYLE_SETTINGS.custom_overlay_path ?? 'examples/overlay';
  const customHeight =
    settings.custom_overlay_height_percent ?? DEFAULT_VISUAL_STYLE_SETTINGS.custom_overlay_height_percent ?? 33;
  const customFit = settings.custom_overlay_fit_mode ?? DEFAULT_VISUAL_STYLE_SETTINGS.custom_overlay_fit_mode ?? 'cover';
  const options = [
    { value: 'preset', label: 'Dùng overlay preset' },
    { value: 'none', label: 'Không dùng overlay' },
    { value: 'custom', label: 'Dùng ảnh custom' },
  ];

  return (
    <div className="mt-4 grid gap-3 rounded-md border border-line bg-white p-3">
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            className={`rounded-md px-3 py-2 text-xs font-semibold ${
              mode === option.value
                ? 'bg-brand text-white'
                : 'border border-line bg-white text-ink hover:border-brand'
            }`}
            type="button"
            onClick={() => onChange({ overlay_mode: option.value })}
          >
            {option.label}
          </button>
        ))}
      </div>

      {mode === 'custom' ? (
        <PathInput
          label="Đường dẫn ảnh/thư mục overlay"
          value={customPath}
          onChange={(custom_overlay_path) => onChange({ custom_overlay_path })}
          placeholder="examples/overlay hoặc D:\\Overlay\\my_overlay.png"
          modes={['file', 'folder']}
          fileExtensions={['.png', '.jpg', '.jpeg', '.webp']}
        />
      ) : null}
      {mode === 'custom' ? (
        <NumberInput
          label="Chiều cao overlay custom (%)"
          value={customHeight}
          min={5}
          max={100}
          onChange={(value) => onChange({ custom_overlay_height_percent: value })}
        />
      ) : null}
      {mode === 'custom' ? (
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-ink">Cách fit overlay custom</span>
          <select
            className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
            value={customFit}
            onChange={(event) => onChange({ custom_overlay_fit_mode: event.target.value })}
          >
            <option value="cover">Phủ đủ ngang, crop phần dư</option>
            <option value="contain">Giữ toàn bộ ảnh</option>
            <option value="stretch">Kéo vừa vùng</option>
          </select>
        </label>
      ) : null}
    </div>
  );
}

function SimpleSettingsPanel({
  config,
  visualStylePresets,
  industryPresets,
  onChange,
}: {
  config: ProjectConfig;
  visualStylePresets: VisualStylePreset[];
  industryPresets: IndustryPreset[];
  onChange: (config: ProjectConfig) => void;
}) {
  const countOption = OUTPUT_COUNT_OPTIONS.find((option) => option.value === config.render.output_count)?.id ?? 'custom';
  const durationValue = DURATION_OPTIONS.some((option) => option.value === config.render.duration)
    ? String(config.render.duration)
    : 'custom';
  const styleValue = findVideoStyle(config.timeline?.template_id)?.id ?? 'custom';
  const editValue = findEditStrength(config.effects)?.id ?? 'custom';
  const voiceValue = findVoice(config.tts?.voice)?.id ?? 'custom';
  const music = config.music ?? DEFAULT_MUSIC_SETTINGS;

  function updateRender(patch: Partial<ProjectConfig['render']>) {
    onChange({ ...config, render: { ...config.render, ...patch } });
  }

  function updateTTS(patch: Partial<NonNullable<ProjectConfig['tts']>>) {
    onChange({ ...config, tts: { ...(config.tts ?? DEFAULT_TTS_SETTINGS), ...patch } });
  }

  function updateMusic(patch: Partial<ProjectConfig['music']>) {
    onChange({ ...config, music: mergeMusicSettings(config.music, patch) });
  }

  function updateCropSafety(patch: Partial<NonNullable<ProjectConfig['crop_safety']>>) {
    onChange({ ...config, crop_safety: { ...(config.crop_safety ?? DEFAULT_CROP_SAFETY_SETTINGS), ...patch } });
  }

  function updateVisualStyle(patch: Partial<VisualStyleSettings>) {
    onChange({
      ...config,
      visual_style: {
        ...(config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS),
        ...patch,
      },
    });
  }

  function updateIndustry(presetId: string) {
    const preset = industryPresets.find((item) => item.id === presetId);
    if (!preset) return;
    onChange(applyIndustryPresetToConfig(config, preset, DEFAULT_INDUSTRY_APPLY_OPTIONS));
  }

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="mb-4 text-base font-semibold text-ink">Chế độ đơn giản</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label="Ngành hàng"
          value={config.industry?.preset_id ?? 'general_product'}
          onChange={updateIndustry}
          options={industryPresets.map((preset) => ({ value: preset.id, label: preset.name }))}
        />
        <SelectField
          label="Số lượng video đầu ra"
          value={countOption}
          onChange={(value) => {
            const option = OUTPUT_COUNT_OPTIONS.find((item) => item.id === value);
            if (option?.value) updateRender({ output_count: option.value });
          }}
          options={OUTPUT_COUNT_OPTIONS.map((option) => ({ value: option.id, label: option.label }))}
        />
        {countOption === 'custom' ? (
          <NumberInput
            label="Số lượng tuỳ chỉnh"
            value={config.render.output_count}
            min={1}
            max={50}
            onChange={(output_count) => updateRender({ output_count: Math.max(1, output_count) })}
          />
        ) : null}
        <SelectField
          label="Độ dài video"
          value={durationValue}
          onChange={(value) => {
            const option = DURATION_OPTIONS.find((item) => String(item.value) === value);
            if (option) updateRender({ duration: option.value });
          }}
          options={[
            ...DURATION_OPTIONS.map((option) => ({ value: String(option.value), label: option.label })),
            ...(durationValue === 'custom' ? [{ value: 'custom', label: `${config.render.duration}s` }] : []),
          ]}
        />
        <SelectField
          label="Phong cách video"
          value={styleValue}
          onChange={(value) => {
            const option = VIDEO_STYLE_OPTIONS.find((item) => item.id === value);
            if (!option) return;
            onChange({
              ...config,
              timeline: { ...(config.timeline ?? { template_id: DEFAULT_TEMPLATE_ID }), template_id: option.templateId },
              visual_style: {
                ...(config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS),
                preset_id: option.visualStylePresetId,
              },
            });
          }}
          options={[
            ...VIDEO_STYLE_OPTIONS.map((option) => ({ value: option.id, label: option.label })),
            ...(styleValue === 'custom' ? [{ value: 'custom', label: config.timeline?.template_id ?? 'Tuỳ chỉnh' }] : []),
          ]}
        />
        <SelectField
          label="Mức độ chỉnh sửa"
          value={editValue}
          onChange={(value) => {
            const option = EDIT_STRENGTH_OPTIONS.find((item) => item.id === value);
            if (option) onChange({ ...config, effects: option.effects });
          }}
          options={[
            ...EDIT_STRENGTH_OPTIONS.map((option) => ({ value: option.id, label: option.label })),
            ...(editValue === 'custom' ? [{ value: 'custom', label: 'Tuỳ chỉnh từ chế độ nâng cao' }] : []),
          ]}
        />
        <SelectField
          label="Giọng đọc"
          value={voiceValue}
          onChange={(value) => {
            const option = VOICE_OPTIONS.find((item) => item.id === value);
            if (!option) return;
            updateTTS({
              provider: option.provider,
              voice: option.voice,
              language: option.language,
              output_format: 'mp3',
            });
          }}
          options={[
            ...VOICE_OPTIONS.map((option) => ({ value: option.id, label: option.label })),
            ...(voiceValue === 'custom' ? [{ value: 'custom', label: config.tts?.voice ?? 'Giọng tuỳ chỉnh' }] : []),
          ]}
        />
        <SelectField
          label="Ngôn ngữ"
          value={config.ai.language || 'vi'}
          onChange={(language) => onChange({ ...config, ai: { ...config.ai, language } })}
          options={[
            { value: 'vi', label: 'Tiếng Việt' },
            { value: 'vi-VN', label: 'Tiếng Việt (vi-VN)' },
          ]}
        />
        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm sm:col-span-2">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={music.enabled}
            onChange={(event) => updateMusic({ enabled: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Bật nhạc nền</span>
            <span className="mt-1 block break-all text-xs text-muted">
              {music.source_file || music.source_folder || DEFAULT_MUSIC_SETTINGS.source_folder}
            </span>
          </span>
        </label>
        {music.enabled ? (
          <div className="grid gap-3 sm:col-span-2 lg:grid-cols-2">
            <PathInput
              label="Thư mục nhạc nền"
              value={music.source_folder ?? ''}
              onChange={(source_folder) => updateMusic({ source_folder, source_file: null })}
              placeholder="examples/music hoặc D:\\Music"
              modes={['folder']}
            />
            <PathInput
              label="File nhạc nền"
              value={music.source_file ?? ''}
              onChange={(source_file) => updateMusic({ source_file, source_folder: null })}
              placeholder="D:\\Music\\track.mp3"
              modes={['file']}
              fileExtensions={['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus']}
            />
          </div>
        ) : null}
        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm sm:col-span-2">
          <input
            className="mt-1 h-4 w-4 accent-brand disabled:opacity-50"
            type="checkbox"
            checked={music.duck_under_voice}
            disabled={!music.enabled}
            onChange={(event) => updateMusic({ duck_under_voice: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Giảm nhạc khi có giọng đọc</span>
            <span className="mt-1 block text-xs text-muted">
              Mặc định tắt để nhạc nền giữ âm lượng đều. Chỉ bật khi giọng đọc bị nhạc lấn át.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm sm:col-span-2">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={config.crop_safety?.enabled ?? DEFAULT_CROP_SAFETY_SETTINGS.enabled}
            onChange={(event) => updateCropSafety({ enabled: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Tự động bảo vệ sản phẩm khi crop</span>
            <span className="mt-1 block text-xs text-muted">
              Tool sẽ hạn chế crop mất sản phẩm, tự dùng nền mờ khi video ngang có chi tiết sát mép.
            </span>
          </span>
        </label>
      </div>
      <div className="mt-5 border-t border-line pt-5">
        <h3 className="mb-3 text-sm font-semibold text-ink">Subtitle / Overlay Style</h3>
        <VisualStyleSelector
          presets={visualStylePresets}
          selectedPresetId={config.visual_style?.preset_id ?? DEFAULT_VISUAL_STYLE_SETTINGS.preset_id}
          resolution={config.render.resolution}
          onSelect={(presetId) => updateVisualStyle({ preset_id: presetId })}
        />
        <OverlayModeControls
          settings={config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS}
          onChange={updateVisualStyle}
        />
      </div>
      <div className="mt-4 rounded-md bg-surface p-3 text-sm text-muted">
        Biến thể kịch bản: <span className="font-semibold text-ink">Tự động trộn</span>
      </div>
    </div>
  );
}

function AdvancedSettingsPanel({
  config,
  presets,
  visualStylePresets,
  industryPresets,
  industryApplyOptions,
  selectedPreset,
  timelineTemplates,
  scriptVariantStyles,
  scriptVariantSummary,
  availableTTSProviders,
  googleVoices,
  loadingGoogleVoices,
  scanResult,
  segmentScoring,
  busy,
  safetyBlocked,
  onPreset,
  onIndustryApplyOptionsChange,
  onIndustrySelect,
  onIndustryPreset,
  onTimelineTemplate,
  onGenerateScriptVariants,
  onTTSProviderChange,
  onTTSChange,
  onLoadGoogleVoices,
  onVisualStyleChange,
  onMusicChange,
  onEffectsChange,
  onCropSafetyChange,
  onRenderChange,
  onScan,
  onBack,
  onRenderPreview,
  onRenderFull,
}: {
  config: ProjectConfig;
  presets: Preset[];
  visualStylePresets: VisualStylePreset[];
  industryPresets: IndustryPreset[];
  industryApplyOptions: ApplyIndustryPresetOptions;
  selectedPreset: string;
  timelineTemplates: TimelineTemplateSummary[];
  scriptVariantStyles: ScriptVariantStyle[];
  scriptVariantSummary: ScriptVariantSummary[];
  availableTTSProviders: TTSProviderInfo[];
  googleVoices: TTSVoiceInfo[];
  loadingGoogleVoices: boolean;
  scanResult: ScanResponse | null;
  segmentScoring: SegmentScoringSummary | null;
  busy: boolean;
  safetyBlocked: boolean;
  onPreset: (preset: Preset) => void;
  onIndustryApplyOptionsChange: (options: ApplyIndustryPresetOptions) => void;
  onIndustrySelect: (presetId: string) => void;
  onIndustryPreset: (presetId: string) => void;
  onTimelineTemplate: (templateId: string) => void;
  onGenerateScriptVariants: () => void;
  onTTSProviderChange: (provider: string) => void;
  onTTSChange: (patch: Partial<NonNullable<ProjectConfig['tts']>>) => void;
  onLoadGoogleVoices: () => void;
  onVisualStyleChange: (patch: Partial<VisualStyleSettings>) => void;
  onMusicChange: (patch: Partial<ProjectConfig['music']>) => void;
  onEffectsChange: (effects: EffectSettings) => void;
  onCropSafetyChange: (patch: Partial<NonNullable<ProjectConfig['crop_safety']>>) => void;
  onRenderChange: (patch: Partial<ProjectConfig['render']>) => void;
  onScan: () => void;
  onBack: () => void;
  onRenderPreview: () => void;
  onRenderFull: () => void;
}) {
  return (
    <>
      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Mẫu cài đặt</h2>
        <PresetSelector presets={presets} selectedName={selectedPreset} onSelect={onPreset} />
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Industry Preset</h2>
        <IndustryPresetSelector
          presets={industryPresets}
          selectedPresetId={config.industry?.preset_id ?? 'general_product'}
          applyOptions={industryApplyOptions}
          onApplyOptionsChange={onIndustryApplyOptionsChange}
          onSelect={onIndustrySelect}
        />
        <div className="mt-3 flex flex-wrap gap-3">
          <button
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            type="button"
            disabled={busy}
            onClick={() => onIndustryPreset(config.industry?.preset_id ?? 'general_product')}
          >
            Apply preset
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            disabled={busy}
            onClick={() => onIndustryPreset('general_product')}
          >
            Reset general
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Phong cách dòng thời gian</h2>
        <select
          className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
          value={config.timeline?.template_id ?? DEFAULT_TEMPLATE_ID}
          onChange={(event) => onTimelineTemplate(event.target.value)}
        >
          {timelineTemplates.map((template) => (
            <option key={template.id} value={template.id}>
              {template.name}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Subtitle / Overlay Style</h2>
        <VisualStyleSelector
          presets={visualStylePresets}
          selectedPresetId={config.visual_style?.preset_id ?? DEFAULT_VISUAL_STYLE_SETTINGS.preset_id}
          resolution={config.render.resolution}
          onSelect={(presetId) => onVisualStyleChange({ preset_id: presetId })}
        />
        <OverlayModeControls
          settings={config.visual_style ?? DEFAULT_VISUAL_STYLE_SETTINGS}
          onChange={onVisualStyleChange}
        />
      </div>

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Biến thể kịch bản</h2>
        <select
          className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
          value="auto_mix"
          onChange={() => undefined}
        >
          <option value="auto_mix">Tự động trộn</option>
        </select>
        <button
          className="mt-3 rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          disabled={busy}
          onClick={onGenerateScriptVariants}
        >
          Tạo biến thể kịch bản
        </button>
        {scriptVariantSummary.length ? (
          <div className="mt-4 max-h-48 overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
            {scriptVariantSummary.map((item) => (
              <div key={item.output_index} className="grid gap-1 border-b border-line py-2 last:border-b-0">
                <span className="font-semibold text-ink">
                  Video {item.output_index}: {formatVariantName(item.variant_style_id, scriptVariantStyles)}
                </span>
                <span>{item.hook}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <TTSPanel
        config={config}
        availableTTSProviders={availableTTSProviders}
        googleVoices={googleVoices}
        loadingGoogleVoices={loadingGoogleVoices}
        onProviderChange={onTTSProviderChange}
        onChange={onTTSChange}
        onLoadGoogleVoices={onLoadGoogleVoices}
      />

      <MusicPanel config={config} onChange={onMusicChange} />

      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h2 className="mb-3 text-base font-semibold text-ink">Hiệu ứng</h2>
        <EffectSliders effects={config.effects} onChange={onEffectsChange} />
      </div>

      <CropSafetyPanel config={config} onChange={onCropSafetyChange} />

      <SESEPanel config={config} onChange={onRenderChange} />

      {scanResult ? <ScanResult scanResult={scanResult} segmentScoring={segmentScoring} /> : null}

      <div className="flex flex-wrap items-center gap-3">
        <button
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          disabled={busy}
          onClick={onBack}
        >
          Quay lại
        </button>
        <button
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          disabled={busy}
          onClick={onScan}
        >
          Quét video
        </button>
        <button
          className="rounded-md bg-slate-700 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          type="button"
          disabled={busy || safetyBlocked}
          onClick={onRenderPreview}
        >
          Render thử
        </button>
        <button
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          type="button"
          disabled={busy || safetyBlocked}
          onClick={onRenderFull}
        >
          Render toàn bộ
        </button>
      </div>
    </>
  );
}

function TTSPanel({
  config,
  availableTTSProviders,
  googleVoices,
  loadingGoogleVoices,
  onProviderChange,
  onChange,
  onLoadGoogleVoices,
}: {
  config: ProjectConfig;
  availableTTSProviders: TTSProviderInfo[];
  googleVoices: TTSVoiceInfo[];
  loadingGoogleVoices: boolean;
  onProviderChange: (provider: string) => void;
  onChange: (patch: Partial<NonNullable<ProjectConfig['tts']>>) => void;
  onLoadGoogleVoices: () => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="mb-3 text-base font-semibold text-ink">Giọng đọc</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <SelectField
          label="Nhà cung cấp"
          value={config.tts?.provider ?? 'edge_tts'}
          onChange={onProviderChange}
          options={availableTTSProviders
            .filter((provider) => provider.id !== 'silent')
            .map((provider) => ({ value: provider.id, label: provider.name }))}
        />
        <SelectField
          label="Dự phòng"
          value={config.tts?.fallback_provider ?? 'piper'}
          onChange={(value) => onChange({ fallback_provider: value })}
          options={availableTTSProviders
            .filter((provider) => provider.id !== 'edge_tts')
            .map((provider) => ({ value: provider.id, label: provider.name }))}
        />
        {config.tts?.provider === 'google_cloud_tts' ? (
          <SelectField
            label="Giọng đọc"
            value={config.tts?.voice ?? 'vi-VN-Wavenet-A'}
            onChange={(value) => onChange({ voice: value })}
            options={[
              { value: config.tts?.voice || 'vi-VN-Wavenet-A', label: config.tts?.voice || 'Tải giọng Google' },
              ...googleVoices.map((voice) => ({
                value: voice.name,
                label: `${voice.name}${voice.ssml_gender ? ` (${voice.ssml_gender})` : ''}`,
              })),
            ]}
          />
        ) : (
          <SelectField
            label="Giọng đọc"
            value={config.tts?.voice ?? 'vi-VN-HoaiMyNeural'}
            onChange={(value) => onChange({ voice: value })}
            options={[
              { value: 'vi-VN-HoaiMyNeural', label: 'vi-VN-HoaiMyNeural' },
              { value: 'vi-VN-NamMinhNeural', label: 'vi-VN-NamMinhNeural' },
            ]}
          />
        )}
        <SelectField
          label="Định dạng"
          value={config.tts?.output_format ?? 'mp3'}
          onChange={(value) => onChange({ output_format: value })}
          options={[
            { value: 'mp3', label: 'MP3' },
            { value: 'wav', label: 'WAV' },
          ]}
        />
        {config.tts?.provider === 'google_cloud_tts' ? (
          <>
            <div className="sm:col-span-2 rounded-md bg-surface p-3 text-xs text-muted">
              API key Google Cloud và file Service Account JSON được quản lý trong trang Cài đặt chung.
            </div>
            <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
              <button
                className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
                type="button"
                disabled={loadingGoogleVoices}
                onClick={onLoadGoogleVoices}
              >
                {loadingGoogleVoices ? 'Đang tải giọng...' : 'Tải giọng Google'}
              </button>
              <span className="text-xs text-muted">
                {googleVoices.length ? `Đã tải ${googleVoices.length} giọng` : 'vi-VN'}
              </span>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function MusicPanel({
  config,
  onChange,
}: {
  config: ProjectConfig;
  onChange: (patch: Partial<ProjectConfig['music']>) => void;
}) {
  const music = config.music ?? DEFAULT_MUSIC_SETTINGS;

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="mb-3 text-base font-semibold text-ink">Nhạc nền</h2>
      <div className="grid gap-3">
        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={music.enabled}
            onChange={(event) => onChange({ enabled: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Bật nhạc nền</span>
            <span className="mt-1 block break-all text-xs text-muted">
              {music.source_file || music.source_folder || 'Chưa cấu hình thư mục nhạc'}
            </span>
          </span>
        </label>

        {music.enabled ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <PathInput
              label="Thư mục nhạc nền"
              value={music.source_folder ?? ''}
              onChange={(source_folder) => onChange({ source_folder, source_file: null })}
              placeholder="examples/music hoặc D:\\Music"
              modes={['folder']}
            />
            <PathInput
              label="File nhạc nền"
              value={music.source_file ?? ''}
              onChange={(source_file) => onChange({ source_file, source_folder: null })}
              placeholder="D:\\Music\\track.mp3"
              modes={['file']}
              fileExtensions={['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus']}
            />
          </div>
        ) : null}

        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm">
          <input
            className="mt-1 h-4 w-4 accent-brand disabled:opacity-50"
            type="checkbox"
            checked={music.duck_under_voice}
            disabled={!music.enabled}
            onChange={(event) => onChange({ duck_under_voice: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Giảm nhạc khi có giọng đọc</span>
            <span className="mt-1 block text-xs text-muted">
              Mặc định tắt. Khi bật, nhạc sẽ nhỏ xuống trong lúc giọng đọc đang đọc.
            </span>
          </span>
        </label>
      </div>
    </div>
  );
}

function CropSafetyPanel({
  config,
  onChange,
}: {
  config: ProjectConfig;
  onChange: (patch: Partial<NonNullable<ProjectConfig['crop_safety']>>) => void;
}) {
  const cropSafety = config.crop_safety ?? DEFAULT_CROP_SAFETY_SETTINGS;

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="mb-3 text-base font-semibold text-ink">Crop Safety</h2>
      <div className="grid gap-3">
        <label className="flex items-start gap-3 rounded-md border border-line bg-white p-3 text-sm">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={cropSafety.enabled}
            onChange={(event) => onChange({ enabled: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Tự động bảo vệ sản phẩm khi crop</span>
            <span className="mt-1 block text-xs text-muted">
              Ưu tiên giữ vùng sản phẩm trong khung 9:16, giảm rủi ro bị overlay hoặc zoom cắt mất.
            </span>
          </span>
        </label>

        <SelectField
          label="Chế độ crop"
          value={cropSafety.mode}
          onChange={(mode) => onChange({ mode })}
          options={[
            { value: 'auto_safe', label: 'Auto Safe' },
            { value: 'center_crop', label: 'Center Crop' },
            { value: 'fit_blur_background', label: 'Fit Blur Background' },
          ]}
        />

        <div className="grid gap-2 sm:grid-cols-2">
          <label className="flex items-start gap-3 rounded-md bg-surface p-3 text-sm">
            <input
              className="mt-1 h-4 w-4 accent-brand"
              type="checkbox"
              checked={cropSafety.allow_blur_background}
              disabled={!cropSafety.enabled}
              onChange={(event) => onChange({ allow_blur_background: event.target.checked })}
            />
            <span>
              <span className="block font-medium text-ink">Cho phép nền mờ</span>
              <span className="mt-1 block text-xs text-muted">Dùng khi video ngang dễ mất chi tiết hai bên.</span>
            </span>
          </label>

          <label className="flex items-start gap-3 rounded-md bg-surface p-3 text-sm">
            <input
              className="mt-1 h-4 w-4 accent-brand"
              type="checkbox"
              checked={cropSafety.reduce_zoom_on_risk}
              disabled={!cropSafety.enabled}
              onChange={(event) => onChange({ reduce_zoom_on_risk: event.target.checked })}
            />
            <span>
              <span className="block font-medium text-ink">Giảm zoom khi rủi ro</span>
              <span className="mt-1 block text-xs text-muted">Hạn chế zoom motion làm sản phẩm tràn khỏi khung.</span>
            </span>
          </label>
        </div>
      </div>
    </div>
  );
}

function SESEPanel({
  config,
  onChange,
}: {
  config: ProjectConfig;
  onChange: (patch: Partial<ProjectConfig['render']>) => void;
}) {
  const sese = config.render;
  const enabled = sese.sese_enabled ?? false;

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Smart Ending Sync (SESE)</h2>
          <p className="mt-1 text-xs text-muted">
            Tự động kéo dài phần cuối video nếu giọng đọc dài hơn timeline, tránh mất câu thoại cuối.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            id="sese-enabled"
            className="h-4 w-4 accent-brand"
            type="checkbox"
            checked={enabled}
            onChange={(e) => onChange({ sese_enabled: e.target.checked })}
          />
          <span className={enabled ? 'font-semibold text-brand' : 'text-muted'}>
            {enabled ? 'Bật' : 'Tắt'}
          </span>
        </label>
      </div>

      {enabled ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <NumberInput
            label="Giới hạn kéo dài tối đa (giây)"
            value={sese.max_auto_extension_seconds ?? 8}
            min={1}
            max={30}
            onChange={(v) => onChange({ max_auto_extension_seconds: v })}
          />
          <NumberInput
            label="Giới hạn tỉ lệ kéo dài (%)"
            value={Math.round((sese.max_auto_extension_ratio ?? 0.4) * 100)}
            min={5}
            max={80}
            onChange={(v) => onChange({ max_auto_extension_ratio: v / 100 })}
          />
          <div className="sm:col-span-2">
            <SelectField
              label="Chế độ SESE"
              value={sese.sese_mode ?? 'auto'}
              onChange={(v) => onChange({ sese_mode: v })}
              options={[
                { value: 'auto', label: 'Tự động (auto) — Khuyến nghị' },
              ]}
            />
          </div>
          <div className="sm:col-span-2">
            <SelectField
              label="Chiến lược khi vượt giới hạn"
              value={sese.sese_failure_strategy ?? 'trim'}
              onChange={(v) => onChange({ sese_failure_strategy: v })}
              options={[
                { value: 'trim', label: 'Cắt giọng đọc ở mức tối đa cho phép (trim)' },
                { value: 'fail', label: 'Báo lỗi và dừng render (fail)' },
              ]}
            />
          </div>
          <div className="sm:col-span-2 rounded-md bg-blue-50 border border-blue-200 p-3 text-xs text-blue-800">
            <strong>Lưu ý:</strong> SESE chỉ hoạt động ở chế độ Render toàn bộ. Render thử sẽ bỏ qua SESE để tăng tốc độ.
          </div>
        </div>
      ) : (
        <div className="mt-2 rounded-md bg-surface p-3 text-xs text-muted">
          Mặc định tắt. Bật khi gặp hiện tượng giọng đọc bị cắt ở câu cuối.
        </div>
      )}
    </div>
  );
}

function PreviewSection({
  job,
  output,
  script,
  cropSafety,
  targetDuration,
  scriptError,
  savingScript,
  onScriptChange,
  onValidationChange,
  onSaveScript,
  onRenderFull,
  onRenderPreviewAgain,
  fullRenderDisabled,
}: {
  job: JobStatus | null;
  output: JobOutput | null;
  script: ProductVideoScript | null;
  cropSafety: CropSafetyAnalyzeResponse | null;
  targetDuration: number;
  scriptError: string | null;
  savingScript: boolean;
  onScriptChange: (script: ProductVideoScript) => void;
  onValidationChange: (valid: boolean, errors: string[]) => void;
  onSaveScript: () => void;
  onRenderFull: () => void;
  onRenderPreviewAgain: () => void;
  fullRenderDisabled: boolean;
}) {
  const done = Boolean(job?.status && DONE_STATUSES.has(job.status));
  const videoSrc = output?.path ? videoFileUrl(output.path) : null;
  const warnings = collectPreviewWarnings(output, job);

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h2 className="text-base font-semibold text-ink">Video thử</h2>
      </div>

      <RenderProgress job={job} />
      <WarningBox warnings={warnings} />
      <CropSafetyStatusBox result={cropSafety} />

      {done && output ? (
        <div className="space-y-3 rounded-md bg-surface p-4">
          <div className="grid gap-2 text-sm md:grid-cols-[110px_1fr]">
            <span className="font-medium text-ink">Trạng thái</span>
            <span className="text-muted">{formatStatus(output.status)}</span>
            <span className="font-medium text-ink">Giọng đọc</span>
            <span className="text-muted">{output.tts_provider ?? '-'}</span>
            <span className="font-medium text-ink">Phụ đề</span>
            <span className="break-all text-muted">{output.subtitle_ass_file ?? output.subtitle_file ?? '-'}</span>
            <span className="font-medium text-ink">Video</span>
            <span className="break-all text-muted">{output.path}</span>
          </div>
          {videoSrc ? <video className="max-h-[520px] w-full rounded-md bg-black" controls src={videoSrc} /> : null}
        </div>
      ) : null}

      {script ? (
        <div className="space-y-4 rounded-lg border border-line bg-white p-5 shadow-panel">
          <ApiErrorBox error={scriptError} />
          <ScriptEditorForm
            script={script}
            targetDuration={targetDuration}
            onChange={onScriptChange}
            onValidationChange={onValidationChange}
          />
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
              type="button"
              disabled={savingScript}
              onClick={onSaveScript}
            >
              {savingScript ? 'Đang lưu...' : 'Lưu kịch bản'}
            </button>
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
              type="button"
              disabled={fullRenderDisabled}
              onClick={onRenderPreviewAgain}
            >
              Render thử lại
            </button>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              type="button"
              disabled={fullRenderDisabled}
              onClick={onRenderFull}
            >
              Render toàn bộ
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function CropSafetyStatusBox({ result }: { result: CropSafetyAnalyzeResponse | null }) {
  if (!result) return null;

  if (!result.success) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <span className="font-semibold">Crop Safety chưa có dữ liệu.</span>
        <span className="mt-1 block">{result.error ?? 'Render preview xong rồi thử lại.'}</span>
      </div>
    );
  }

  const warnings = result.warnings_summary ?? {};
  const warningEntries = Object.entries(warnings);
  const score = result.average_crop_safety_score ?? 0;
  const scoreLabel = `${Math.round(score * 100)}%`;
  const badgeClass =
    score >= 0.78
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : score >= 0.60
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : 'border-red-200 bg-red-50 text-red-700';

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Crop Safety</h2>
          <p className="mt-1 text-sm text-muted">
            Đã phân tích {result.total_clips_analyzed ?? 0} cảnh trong video thử.
          </p>
        </div>
        <span className={`rounded-md border px-3 py-1.5 text-sm font-semibold ${badgeClass}`}>
          Điểm an toàn {scoreLabel}
        </span>
      </div>

      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Metric label="Cảnh dùng nền mờ" value={result.fallback_to_blur_background ?? 0} />
        <Metric label="Số cảnh báo crop" value={warningEntries.reduce((total, [, count]) => total + count, 0)} />
      </div>

      {warningEntries.length ? (
        <ul className="mt-3 space-y-2 text-sm">
          {warningEntries.slice(0, 6).map(([warning, count]) => (
            <li className="rounded-md bg-surface px-3 py-2 text-muted" key={warning}>
              <span className="font-semibold text-ink">{count}x</span> {formatCropWarning(warning)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function FriendlySummary({
  config,
  providers,
  templates,
  visualStylePresets,
  industryPresets,
}: {
  config: ProjectConfig;
  providers: TTSProviderInfo[];
  templates: TimelineTemplateSummary[];
  visualStylePresets: VisualStylePreset[];
  industryPresets: IndustryPreset[];
}) {
  const style = findVideoStyle(config.timeline?.template_id);
  const edit = findEditStrength(config.effects);
  const voice = findVoice(config.tts?.voice);
  const provider = providers.find((item) => item.id === (config.tts?.provider ?? 'edge_tts'));
  const template = templates.find((item) => item.id === config.timeline?.template_id);
  const visualStyle = visualStylePresets.find(
    (item) => item.id === (config.visual_style?.preset_id ?? DEFAULT_VISUAL_STYLE_SETTINGS.preset_id),
  );
  const industry = industryPresets.find((item) => item.id === (config.industry?.preset_id ?? 'general_product'));
  const cropSafety = config.crop_safety ?? DEFAULT_CROP_SAFETY_SETTINGS;
  const musicSummary = !config.music.enabled
      ? 'Tắt'
    : config.music.duck_under_voice
      ? 'Bật, giảm nhạc khi có giọng đọc'
      : 'Bật, giữ âm lượng đều';

  return (
    <dl className="grid gap-3 text-sm">
      <SummaryRow label="Dự án" value={config.product.name || config.project_name} />
      <SummaryRow label="Industry" value={industry?.name ?? config.industry?.preset_id ?? 'general_product'} />
      <SummaryRow label="Đầu ra" value={`${config.render.output_count} video x ${config.render.duration}s`} />
      <SummaryRow label="Phong cách" value={style?.summaryLabel ?? config.timeline?.template_id ?? 'Tuỳ chỉnh'} />
      <SummaryRow label="Mức chỉnh sửa" value={edit?.summaryLabel ?? 'Tuỳ chỉnh'} />
      <SummaryRow label="Giọng đọc" value={voice?.summaryLabel ?? config.tts?.voice ?? '-'} />
      <SummaryRow label="Tạo giọng đọc" value={provider?.name ?? config.tts?.provider ?? '-'} />
      <SummaryRow label="Nhạc nền" value={musicSummary} />
      <SummaryRow label="Crop Safety" value={cropSafety.enabled ? `Bật (${cropSafety.mode})` : 'Tắt'} />
      <SummaryRow label="Dòng thời gian" value={template?.name ?? config.timeline?.template_id ?? '-'} />
      <SummaryRow label="Kịch bản" value="Tự động trộn" />
      <SummaryRow label="Subtitle / Overlay" value={visualStyle?.name ?? config.visual_style?.preset_id ?? '-'} />
    </dl>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 rounded-md bg-surface p-3">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="font-semibold text-ink">{value}</dd>
    </div>
  );
}

function ScanResult({
  scanResult,
  segmentScoring,
}: {
  scanResult: ScanResponse;
  segmentScoring: SegmentScoringSummary | null;
}) {
  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="text-base font-semibold text-ink">Kết quả quét video</h2>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
        <Metric label="Tổng số file" value={scanResult.total_files} />
        <Metric label="Video hợp lệ" value={scanResult.valid_videos} />
        <Metric label="File không hợp lệ" value={scanResult.invalid_files} />
      </div>
      {segmentScoring ? (
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
          <Metric label="Tổng cảnh" value={segmentScoring.total_segments} />
          <Metric label="Cảnh dùng được" value={segmentScoring.usable_segments} />
          <Metric label="Cảnh bị loại" value={segmentScoring.rejected_segments} />
          <Metric label="Điểm trung bình" value={segmentScoring.average_score.toFixed(2)} />
        </div>
      ) : null}
      <div className="mt-4 max-h-56 overflow-auto rounded-md bg-surface p-3 text-xs text-muted">
        {scanResult.media.map((item) => (
          <div key={item.path} className="break-all py-1">
            {item.path}
          </div>
        ))}
      </div>
    </div>
  );
}

function ProductSafetyBox({
  result,
  checking,
  onRun,
}: {
  result: SafetyCheckResult | null;
  checking: boolean;
  onRun: () => void;
}) {
  const status = result
    ? result.errors_count > 0
      ? 'error'
      : result.warnings_count > 0
        ? 'warning'
        : 'passed'
    : 'idle';
  const statusText =
    status === 'passed'
      ? 'Thông tin sản phẩm đủ để render'
      : status === 'warning'
        ? `Có ${result?.warnings_count ?? 0} cảnh báo cần xem lại`
        : status === 'error'
          ? `Có ${result?.errors_count ?? 0} lỗi cần sửa trước khi render`
          : 'Chưa chạy Product Info QA';
  const badgeClass =
    status === 'passed'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : status === 'warning'
        ? 'bg-amber-50 text-amber-800 border-amber-200'
        : status === 'error'
          ? 'bg-red-50 text-red-700 border-red-200'
          : 'bg-surface text-muted border-line';

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Product Info QA</h2>
          <p className="mt-1 text-sm text-muted">
            Kiểm tra thông tin sản phẩm, claim rủi ro và điều kiện render cơ bản.
          </p>
        </div>
        <button
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          disabled={checking}
          onClick={onRun}
        >
          {checking ? 'Đang kiểm tra...' : 'Run Safety Check'}
        </button>
      </div>

      <div className={`mt-4 rounded-md border px-3 py-2 text-sm font-semibold ${badgeClass}`}>
        {statusText}
      </div>

      {result?.warnings_count ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Warning không chặn render. Bạn vẫn có thể tiếp tục render với cảnh báo sau khi đã kiểm tra nội dung.
        </p>
      ) : null}

      {result?.issues.length ? (
        <ul className="mt-3 max-h-56 space-y-2 overflow-auto text-sm">
          {result.issues.map((issue, index) => (
            <li
              className={`rounded-md border px-3 py-2 ${
                issue.severity === 'error'
                  ? 'border-red-200 bg-red-50 text-red-700'
                  : issue.severity === 'warning'
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : 'border-line bg-surface text-muted'
              }`}
              key={`${issue.category}-${issue.field ?? 'field'}-${index}`}
            >
              <span className="font-semibold">{issue.severity.toUpperCase()}</span>
              {issue.field ? <span className="ml-1 text-xs opacity-80">({issue.field})</span> : null}
              <span className="block">{issue.message}</span>
              {issue.suggestion ? <span className="mt-1 block text-xs opacity-80">{issue.suggestion}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SourceMediaSummaryBox({
  summary,
  onManage,
}: {
  summary: SourceMediaSummary | null;
  onManage: () => void;
}) {
  const usableSegments = summary?.usable_segments ?? 0;
  const totalMedia = summary?.total_media ?? 0;
  const excludedMedia = summary?.excluded_media ?? 0;
  const favoriteSegments = summary?.favorite_segments ?? 0;
  const lowSegmentWarning = Boolean(summary && usableSegments > 0 && usableSegments < 6);

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Source media</h2>
          <p className="mt-1 text-sm text-muted">
            {summary
              ? `${totalMedia} videos, ${excludedMedia} excluded, ${usableSegments} usable segments, ${favoriteSegments} favorite`
              : 'Chưa có summary. Hãy quét video hoặc mở Source Media Manager.'}
          </p>
        </div>
        <button
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          onClick={onManage}
        >
          Manage Source Media
        </button>
      </div>
      {lowSegmentWarning ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Số segment khả dụng hơi ít. Bạn có thể thêm video nguồn hoặc bỏ exclude một số segment.
        </p>
      ) : null}
    </div>
  );
}

function ProductAssetsSummaryBox({
  assets,
  onManage,
  onPromptPack,
}: {
  assets: ProductAsset[];
  onManage: () => void;
  onPromptPack: () => void;
}) {
  const downloaded = assets.filter((asset) => asset.status === 'downloaded' && asset.is_selected);
  const main = downloaded.find((asset) => asset.role === 'main_product');
  const references = downloaded.filter((asset) => asset.role === 'reference').length;
  const posters = downloaded.filter((asset) => asset.role === 'poster').length;

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Product Assets</h2>
          <p className="mt-1 text-sm text-muted">
            Main product image: {main?.filename || 'N/A'} · Reference images: {references} · Poster images: {posters}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            type="button"
            onClick={onPromptPack}
          >
            Prompt Pack
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            onClick={onManage}
          >
            Manage Assets
          </button>
        </div>
      </div>
      {!downloaded.length ? (
        <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Project chưa có ảnh sản phẩm local. Bạn có thể import ảnh từ Product Draft trước khi render.
        </p>
      ) : null}
    </div>
  );
}

function CachePanel({
  config,
  summary,
  busy,
  message,
  onChange,
  onRefresh,
  onClear,
}: {
  config: ProjectConfig;
  summary: CacheSummary | null;
  busy: boolean;
  message: string | null;
  onChange: (patch: Partial<NonNullable<ProjectConfig['cache']>>) => void;
  onRefresh: () => void;
  onClear: () => void;
}) {
  const cache = config.cache ?? DEFAULT_CACHE_SETTINGS;
  const items = summary?.items ?? {};
  const itemCount = Object.values(items).reduce((total, count) => total + count, 0);

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Performance Cache</h2>
          <p className="mt-1 text-sm text-muted">
            Tái sử dụng metadata, crop safety, TTS và overlay khi input chưa thay đổi.
          </p>
        </div>
        <span
          className={`rounded-md border px-3 py-1.5 text-sm font-semibold ${
            cache.enabled
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-line bg-surface text-muted'
          }`}
        >
          {cache.enabled ? 'Đang bật' : 'Đang tắt'}
        </span>
      </div>

      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
        <Metric label="Cache hit" value={summary?.hits ?? 0} />
        <Metric label="Cache miss" value={summary?.misses ?? 0} />
        <Metric label="Dung lượng" value={formatCacheSize(summary?.cache_size_mb ?? 0)} />
        <Metric label="Số mục" value={itemCount} />
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <label className="flex items-start gap-3 rounded-md bg-surface p-3 text-sm">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={cache.enabled}
            onChange={(event) => onChange({ enabled: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Bật cache render</span>
            <span className="mt-1 block text-xs text-muted">Giúp preview và render lại nhanh hơn.</span>
          </span>
        </label>
        <label className="flex items-start gap-3 rounded-md bg-surface p-3 text-sm">
          <input
            className="mt-1 h-4 w-4 accent-brand"
            type="checkbox"
            checked={cache.clear_cache_before_render}
            disabled={!cache.enabled}
            onChange={(event) => onChange({ clear_cache_before_render: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Xoá cache trước render</span>
            <span className="mt-1 block text-xs text-muted">Dùng khi nghi cache cũ gây sai kết quả.</span>
          </span>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          disabled={busy}
          onClick={onRefresh}
        >
          Làm mới
        </button>
        <button
          className="rounded-md border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50"
          type="button"
          disabled={busy}
          onClick={onClear}
        >
          {busy ? 'Đang xoá...' : 'Xoá cache'}
        </button>
        {message ? <span className="self-center text-sm text-emerald-700">{message}</span> : null}
      </div>
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-xs font-medium text-muted">{label}</span>
      <select
        className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function formatCacheSize(sizeMb: number): string {
  if (sizeMb >= 1024) return `${(sizeMb / 1024).toFixed(2)} GB`;
  return `${sizeMb.toFixed(1)} MB`;
}

function mergeMusicSettings(
  current: ProjectConfig['music'] | undefined,
  patch: Partial<ProjectConfig['music']>,
): ProjectConfig['music'] {
  const next = { ...DEFAULT_MUSIC_SETTINGS, ...(current ?? {}), ...patch };
  if (patch.enabled === true && !next.source_file && !next.source_folder) {
    next.source_folder = DEFAULT_MUSIC_SETTINGS.source_folder;
  }
  return next;
}

function findVideoStyle(templateId?: string | null) {
  return VIDEO_STYLE_OPTIONS.find((option) => option.templateId === templateId);
}

function findEditStrength(effects: EffectSettings) {
  return EDIT_STRENGTH_OPTIONS.find((option) => effectsMatch(effects, option.effects));
}

function findVoice(voice?: string | null) {
  return VOICE_OPTIONS.find((option) => option.voice === voice);
}

function formatVariantName(styleId: string, styles: ScriptVariantStyle[]): string {
  return styles.find((style) => style.id === styleId)?.name ?? styleId;
}

function formatStatus(status: string): string {
  const labels: Record<string, string> = {
    success: 'Thành công',
    warning: 'Có cảnh báo',
    failed: 'Thất bại',
    completed: 'Hoàn thành',
    completed_with_errors: 'Hoàn thành nhưng có lỗi',
    running: 'Đang chạy',
    queued: 'Đang chờ',
  };
  return labels[status.toLowerCase()] ?? status;
}

function collectPreviewWarnings(output: JobOutput | null, job: JobStatus | null): string[] {
  const outputWarnings = output?.warnings ?? [];
  const cropWarnings = output?.crop_safety?.warnings ?? [];
  const logWarnings = (job?.logs ?? [])
    .filter((log) => log.level.toLowerCase() === 'warning')
    .map((log) => log.message);
  return Array.from(new Set([...outputWarnings, ...cropWarnings, ...logWarnings]));
}

function formatCropWarning(warning: string): string {
  const labels: Record<string, string> = {
    important_content_near_edge: 'Nội dung quan trọng nằm gần mép khung',
    landscape_video_may_lose_side_content: 'Video ngang có thể mất chi tiết hai bên',
    overlay_may_cover_important_content: 'Overlay đáy có thể che vùng quan trọng',
    zoom_motion_may_cut_content: 'Zoom motion có thể cắt mất sản phẩm',
    blur_background_disabled_fallback_center_crop: 'Nền mờ đang tắt nên dùng crop giữa',
  };
  return labels[warning] ?? warning;
}

function googleLanguageCode(voice?: string, language?: string): string {
  if (voice && voice.split('-').length >= 3) return voice.split('-').slice(0, 2).join('-');
  if (!language || language.toLowerCase() === 'vi') return 'vi-VN';
  return language;
}
