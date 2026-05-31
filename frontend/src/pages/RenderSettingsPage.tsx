import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  analyzeProjectSegments,
  createProject,
  generateScriptVariants,
  getGoogleCloudTTSVoices,
  getJobResults,
  getJobStatus,
  getLatestScript,
  getPresets,
  getProject,
  getScriptVariantStyles,
  getTTSProviders,
  getTimelineTemplates,
  saveProjectScript,
  scanProject,
  startRender,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import EffectSliders from '../components/EffectSliders';
import NumberInput from '../components/NumberInput';
import PresetSelector from '../components/PresetSelector';
import RenderProgress from '../components/RenderProgress';
import WarningBox from '../components/WarningBox';
import ScriptEditorForm from '../components/script/ScriptEditorForm';
import { DEFAULT_MUSIC_SETTINGS, DEFAULT_TTS_SETTINGS } from '../config/defaults';
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
  JobOutput,
  JobStatus,
  Preset,
  ProductVideoScript,
  ProjectConfig,
  ScanResponse,
  SegmentScoringSummary,
  ScriptVariantStyle,
  ScriptVariantSummary,
  TimelineTemplateSummary,
  TTSProviderInfo,
  TTSVoiceInfo,
} from '../types/project';
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
  const [ttsProviders, setTTSProviders] = useState<TTSProviderInfo[]>([]);
  const [googleVoices, setGoogleVoices] = useState<TTSVoiceInfo[]>([]);
  const [loadingGoogleVoices, setLoadingGoogleVoices] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('Balanced Recut');
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [segmentScoring, setSegmentScoring] = useState<SegmentScoringSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [previewJobId, setPreviewJobId] = useState<string | null>(null);
  const [previewProjectId, setPreviewProjectId] = useState<string | null>(null);
  const [previewJob, setPreviewJob] = useState<JobStatus | null>(null);
  const [previewOutput, setPreviewOutput] = useState<JobOutput | null>(null);
  const [script, setScript] = useState<ProductVideoScript | null>(null);
  const [scriptValid, setScriptValid] = useState(true);
  const [scriptErrors, setScriptErrors] = useState<string[]>([]);
  const [scriptError, setScriptError] = useState<string | null>(null);
  const [savingScript, setSavingScript] = useState(false);

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

  function setEditableScript(nextScript: ProductVideoScript) {
    setScript(nextScript);
    setScriptValid(true);
    setScriptErrors([]);
    setScriptError(null);
  }

  function updateConfig(nextConfig: ProjectConfig) {
    setConfig(nextConfig);
    setDirty(true);
    if (projectId) saveProjectConfig(projectId, nextConfig, true);
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể quét video.');
    } finally {
      setBusy(false);
    }
  }

  async function handleRender(previewOnly: boolean) {
    setBusy(true);
    setError(null);
    setScriptError(null);
    try {
      const activeProjectId = await ensureCurrentProject();
      const response = await startRender(activeProjectId, previewOnly);
      if (previewOnly) {
        setPreviewProjectId(activeProjectId);
        setPreviewJobId(response.job_id);
        setPreviewJob(null);
        setPreviewOutput(null);
        setScript(null);
        return;
      }
      navigate(`/queue/${activeProjectId}/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu render.');
      setBusy(false);
    }
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
          <ModeToggle mode={mode} onChange={handleModeChange} />
          <div className="rounded bg-white px-3 py-2 text-xs text-muted shadow-sm">
            {dirty ? 'Dự án có thay đổi chưa lưu' : 'Dự án đã đồng bộ'}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <section className="space-y-5">
          {mode === 'simple' ? (
            <SimpleSettingsPanel config={config} onChange={updateConfig} />
          ) : (
            <AdvancedSettingsPanel
              config={config}
              presets={presets}
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
              onPreset={handlePreset}
              onTimelineTemplate={handleTimelineTemplate}
              onGenerateScriptVariants={handleGenerateScriptVariants}
              onTTSProviderChange={handleTTSProviderChange}
              onTTSChange={updateTTS}
              onLoadGoogleVoices={handleLoadGoogleVoices}
              onEffectsChange={(effects) => updateConfig({ ...config, effects })}
              onMusicChange={(patch) =>
                updateConfig({ ...config, music: { ...(config.music ?? DEFAULT_MUSIC_SETTINGS), ...patch } })
              }
              onScan={handleScan}
              onBack={() => navigate('/')}
              onRenderPreview={() => handleRender(true)}
              onRenderFull={() => handleRender(false)}
            />
          )}

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
                disabled={busy}
                onClick={() => handleRender(true)}
              >
                Render thử
              </button>
              <button
                className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                type="button"
                disabled={busy}
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
              fullRenderDisabled={busy || savingScript}
            />
          ) : null}
        </section>

        <aside className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h2 className="mb-3 text-base font-semibold text-ink">Tóm tắt cấu hình</h2>
          {mode === 'simple' ? (
            <FriendlySummary config={config} providers={availableTTSProviders} templates={timelineTemplates} />
          ) : (
            <pre className="max-h-[780px] overflow-auto rounded-md bg-surface p-4 text-xs leading-relaxed text-ink">
              {previewJson}
            </pre>
          )}
        </aside>
      </div>
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

function SimpleSettingsPanel({
  config,
  onChange,
}: {
  config: ProjectConfig;
  onChange: (config: ProjectConfig) => void;
}) {
  const countOption = OUTPUT_COUNT_OPTIONS.find((option) => option.value === config.render.output_count)?.id ?? 'custom';
  const durationValue = DURATION_OPTIONS.some((option) => option.value === config.render.duration)
    ? String(config.render.duration)
    : 'custom';
  const styleValue = findVideoStyle(config.timeline?.template_id)?.id ?? 'custom';
  const editValue = findEditStrength(config.effects)?.id ?? 'custom';
  const voiceValue = findVoice(config.tts?.voice)?.id ?? 'custom';

  function updateRender(patch: Partial<ProjectConfig['render']>) {
    onChange({ ...config, render: { ...config.render, ...patch } });
  }

  function updateTTS(patch: Partial<NonNullable<ProjectConfig['tts']>>) {
    onChange({ ...config, tts: { ...(config.tts ?? DEFAULT_TTS_SETTINGS), ...patch } });
  }

  function updateMusic(patch: Partial<ProjectConfig['music']>) {
    onChange({ ...config, music: { ...(config.music ?? DEFAULT_MUSIC_SETTINGS), ...patch } });
  }

  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="mb-4 text-base font-semibold text-ink">Chế độ đơn giản</h2>
      <div className="grid gap-4 sm:grid-cols-2">
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
            checked={config.music?.duck_under_voice ?? false}
            onChange={(event) => updateMusic({ duck_under_voice: event.target.checked })}
          />
          <span>
            <span className="block font-medium text-ink">Giảm nhạc khi có giọng đọc</span>
            <span className="mt-1 block text-xs text-muted">
              Mặc định tắt để nhạc nền giữ âm lượng đều. Chỉ bật khi giọng đọc bị nhạc lấn át.
            </span>
          </span>
        </label>
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
  onPreset,
  onTimelineTemplate,
  onGenerateScriptVariants,
  onTTSProviderChange,
  onTTSChange,
  onLoadGoogleVoices,
  onMusicChange,
  onEffectsChange,
  onScan,
  onBack,
  onRenderPreview,
  onRenderFull,
}: {
  config: ProjectConfig;
  presets: Preset[];
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
  onPreset: (preset: Preset) => void;
  onTimelineTemplate: (templateId: string) => void;
  onGenerateScriptVariants: () => void;
  onTTSProviderChange: (provider: string) => void;
  onTTSChange: (patch: Partial<NonNullable<ProjectConfig['tts']>>) => void;
  onLoadGoogleVoices: () => void;
  onMusicChange: (patch: Partial<ProjectConfig['music']>) => void;
  onEffectsChange: (effects: EffectSettings) => void;
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
          disabled={busy}
          onClick={onRenderPreview}
        >
          Render thử
        </button>
        <button
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          type="button"
          disabled={busy}
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

function PreviewSection({
  job,
  output,
  script,
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

function FriendlySummary({
  config,
  providers,
  templates,
}: {
  config: ProjectConfig;
  providers: TTSProviderInfo[];
  templates: TimelineTemplateSummary[];
}) {
  const style = findVideoStyle(config.timeline?.template_id);
  const edit = findEditStrength(config.effects);
  const voice = findVoice(config.tts?.voice);
  const provider = providers.find((item) => item.id === (config.tts?.provider ?? 'edge_tts'));
  const template = templates.find((item) => item.id === config.timeline?.template_id);
  const musicSummary = !config.music.enabled
      ? 'Tắt'
    : config.music.duck_under_voice
      ? 'Bật, giảm nhạc khi có giọng đọc'
      : 'Bật, giữ âm lượng đều';

  return (
    <dl className="grid gap-3 text-sm">
      <SummaryRow label="Dự án" value={config.product.name || config.project_name} />
      <SummaryRow label="Đầu ra" value={`${config.render.output_count} video x ${config.render.duration}s`} />
      <SummaryRow label="Phong cách" value={style?.summaryLabel ?? config.timeline?.template_id ?? 'Tuỳ chỉnh'} />
      <SummaryRow label="Mức chỉnh sửa" value={edit?.summaryLabel ?? 'Tuỳ chỉnh'} />
      <SummaryRow label="Giọng đọc" value={voice?.summaryLabel ?? config.tts?.voice ?? '-'} />
      <SummaryRow label="Tạo giọng đọc" value={provider?.name ?? config.tts?.provider ?? '-'} />
      <SummaryRow label="Nhạc nền" value={musicSummary} />
      <SummaryRow label="Dòng thời gian" value={template?.name ?? config.timeline?.template_id ?? '-'} />
      <SummaryRow label="Kịch bản" value="Tự động trộn" />
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
  const logWarnings = (job?.logs ?? [])
    .filter((log) => log.level.toLowerCase() === 'warning')
    .map((log) => log.message);
  return Array.from(new Set([...outputWarnings, ...logWarnings]));
}

function googleLanguageCode(voice?: string, language?: string): string {
  if (voice && voice.split('-').length >= 3) return voice.split('-').slice(0, 2).join('-');
  if (!language || language.toLowerCase() === 'vi') return 'vi-VN';
  return language;
}
