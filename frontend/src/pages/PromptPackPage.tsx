import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  generateReferenceSummary,
  generateVideoPromptPack,
  getProject,
  listProjectAssets,
  productAssetFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import type {
  ProductAsset,
  ProductReferenceSummary,
  ProjectDetail,
  StoryboardScene,
  VideoPromptPack,
} from '../types/project';

type PromptTab = 'full' | 'short' | 'negative' | 'json';

const styleOptions = [
  { value: 'product_showcase', label: 'Product showcase' },
  { value: 'ugc_review', label: 'UGC review' },
  { value: 'problem_solution', label: 'Problem solution' },
  { value: 'infographic_motion', label: 'Infographic motion' },
];

const modelOptions = [
  { value: 'generic', label: 'Generic' },
  { value: 'omni', label: 'Omni' },
  { value: 'kling', label: 'Kling' },
  { value: 'runway', label: 'Runway' },
  { value: 'veo', label: 'Veo' },
];

export default function PromptPackPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [assets, setAssets] = useState<ProductAsset[]>([]);
  const [summary, setSummary] = useState<ProductReferenceSummary | null>(null);
  const [promptPack, setPromptPack] = useState<VideoPromptPack | null>(null);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [duration, setDuration] = useState(8);
  const [sceneCount, setSceneCount] = useState(5);
  const [style, setStyle] = useState('product_showcase');
  const [modelHint, setModelHint] = useState('omni');
  const [tab, setTab] = useState<PromptTab>('full');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    Promise.all([getProject(projectId), listProjectAssets(projectId), generateReferenceSummary(projectId)])
      .then(([projectResult, assetsResult, summaryResult]) => {
        setProject(projectResult);
        setAssets(assetsResult.items);
        setSummary(summaryResult.summary);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải Prompt Pack.'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const selectedAssets = useMemo(
    () => assets.filter((asset) => asset.status !== 'skipped' && asset.is_selected),
    [assets],
  );
  const mainAsset = useMemo(
    () =>
      selectedAssets.find((asset) => asset.id === summary?.main_product_asset_id) ??
      selectedAssets.find((asset) => asset.role === 'main_product') ??
      null,
    [selectedAssets, summary],
  );
  const referenceCount = selectedAssets.filter((asset) => asset.role === 'reference').length;

  async function handleGenerate() {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await generateVideoPromptPack(projectId, {
        duration_seconds: duration,
        scene_count: sceneCount,
        style,
        model_hint: modelHint === 'generic' ? null : modelHint,
      });
      setPromptPack(response.prompt_pack);
      setSummary(response.prompt_pack.product_reference_summary);
      setFiles(response.files);
      setTab('full');
      setMessage('Đã tạo Prompt Pack và export files.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo Prompt Pack.');
    } finally {
      setBusy(false);
    }
  }

  async function copyText(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    setMessage(`Đã copy ${label}.`);
  }

  const outputText = promptPack ? promptTextForTab(promptPack, tab) : '';

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Prompt Pack</h1>
          <p className="mt-1 text-sm text-muted">{project?.config.project_name ?? projectId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            onClick={() => navigate(projectId ? `/projects/${projectId}/assets` : '/')}
          >
            Manage Assets
          </button>
          <Link
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            to={projectId ? `/settings/${projectId}` : '/'}
          >
            Back to Settings
          </Link>
        </div>
      </div>

      <ApiErrorBox error={error} />
      {message ? <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div> : null}

      {loading ? (
        <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
          Đang tải Prompt Pack...
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(420px,1.05fr)]">
          <section className="space-y-5">
            <ProductReferencePanel
              project={project}
              summary={summary}
              mainAsset={mainAsset}
              referenceCount={referenceCount}
              selectedAssets={selectedAssets}
              projectId={projectId}
            />
            <GenerateOptionsPanel
              duration={duration}
              sceneCount={sceneCount}
              style={style}
              modelHint={modelHint}
              busy={busy}
              onDuration={setDuration}
              onSceneCount={setSceneCount}
              onStyle={setStyle}
              onModelHint={setModelHint}
              onGenerate={() => void handleGenerate()}
            />
            {promptPack ? <StoryboardPreview scenes={promptPack.storyboard.scenes} /> : null}
          </section>

          <section className="space-y-5">
            <PromptOutputPanel
              activeTab={tab}
              promptPack={promptPack}
              outputText={outputText}
              files={files}
              busy={busy}
              onTab={setTab}
              onCopy={(value, label) => void copyText(value, label)}
              onExport={() => void handleGenerate()}
            />
          </section>
        </div>
      )}
    </main>
  );
}

function ProductReferencePanel({
  project,
  summary,
  mainAsset,
  referenceCount,
  selectedAssets,
  projectId,
}: {
  project: ProjectDetail | null;
  summary: ProductReferenceSummary | null;
  mainAsset: ProductAsset | null;
  referenceCount: number;
  selectedAssets: ProductAsset[];
  projectId?: string;
}) {
  const product = project?.config.product;
  const previewUrl = mainAsset?.local_path ? productAssetFileUrl(mainAsset.id) : mainAsset?.original_url || '';
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="text-base font-semibold text-ink">Product Reference</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-[160px_minmax(0,1fr)]">
        <div className="aspect-square overflow-hidden rounded-md border border-line bg-surface">
          {previewUrl ? <img className="h-full w-full object-contain" src={previewUrl} alt={mainAsset?.filename || 'Main product'} /> : null}
        </div>
        <div className="grid gap-2 text-sm">
          <InfoRow label="Product name" value={product?.name ?? '-'} />
          <InfoRow label="Brand" value={product?.brand || '-'} />
          <InfoRow label="Industry" value={project?.config.industry?.preset_id ?? '-'} />
          <InfoRow label="Main product image" value={mainAsset?.filename || mainAsset?.id || 'N/A'} />
          <InfoRow label="Reference image count" value={String(referenceCount)} />
          <InfoRow label="Selected assets" value={String(selectedAssets.length)} />
        </div>
      </div>
      {!mainAsset ? (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Chưa chọn ảnh sản phẩm chính. Prompt Pack vẫn chạy, nhưng nên đặt một ảnh là Main Product để khóa hình ảnh tốt hơn.
          {projectId ? (
            <Link className="ml-2 font-semibold text-amber-900 underline" to={`/projects/${projectId}/assets`}>
              Manage Assets
            </Link>
          ) : null}
        </div>
      ) : null}
      {summary?.warnings.length ? (
        <ul className="mt-4 space-y-1 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {summary.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function GenerateOptionsPanel({
  duration,
  sceneCount,
  style,
  modelHint,
  busy,
  onDuration,
  onSceneCount,
  onStyle,
  onModelHint,
  onGenerate,
}: {
  duration: number;
  sceneCount: number;
  style: string;
  modelHint: string;
  busy: boolean;
  onDuration: (value: number) => void;
  onSceneCount: (value: number) => void;
  onStyle: (value: string) => void;
  onModelHint: (value: string) => void;
  onGenerate: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="text-base font-semibold text-ink">Generate Options</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <SelectField
          label="Duration"
          value={String(duration)}
          onChange={(value) => onDuration(Number(value))}
          options={[
            { value: '8', label: '8s' },
            { value: '10', label: '10s' },
          ]}
        />
        <label className="grid gap-1 text-sm">
          <span className="font-medium text-ink">Scene count</span>
          <input
            className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
            type="number"
            min={1}
            max={12}
            value={sceneCount}
            onChange={(event) => onSceneCount(Math.max(1, Number(event.target.value) || 5))}
          />
        </label>
        <SelectField label="Prompt style" value={style} onChange={onStyle} options={styleOptions} />
        <SelectField label="Model hint" value={modelHint} onChange={onModelHint} options={modelOptions} />
      </div>
      <button
        className="mt-5 rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
        type="button"
        disabled={busy}
        onClick={onGenerate}
      >
        {busy ? 'Đang tạo...' : 'Generate Prompt Pack'}
      </button>
    </section>
  );
}

function StoryboardPreview({ scenes }: { scenes: StoryboardScene[] }) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <h2 className="text-base font-semibold text-ink">Storyboard Preview</h2>
      <div className="mt-4 space-y-3">
        {scenes.map((scene) => (
          <article className="rounded-md border border-line bg-surface p-3" key={scene.scene_index}>
            <div className="text-sm font-semibold text-ink">
              Scene {scene.scene_index} - {scene.scene_type} - {scene.duration_seconds}s
            </div>
            <InfoBlock label="Visual" value={scene.visual_description} />
            <InfoBlock label="Camera" value={scene.camera_direction} />
            <InfoBlock label="Accuracy notes" value={scene.product_accuracy_notes.join('\n')} />
          </article>
        ))}
      </div>
    </section>
  );
}

function PromptOutputPanel({
  activeTab,
  promptPack,
  outputText,
  files,
  busy,
  onTab,
  onCopy,
  onExport,
}: {
  activeTab: PromptTab;
  promptPack: VideoPromptPack | null;
  outputText: string;
  files: Record<string, string>;
  busy: boolean;
  onTab: (tab: PromptTab) => void;
  onCopy: (value: string, label: string) => void;
  onExport: () => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">Prompt Output</h2>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={!promptPack} onClick={() => onCopy(promptPack?.video_prompt || '', 'Full Prompt')}>
            Copy Full Prompt
          </button>
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={!promptPack} onClick={() => onCopy(promptPack?.negative_prompt || '', 'Negative Prompt')}>
            Copy Negative Prompt
          </button>
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" type="button" disabled={!promptPack} onClick={() => onCopy(JSON.stringify(promptPack?.json_prompt ?? {}, null, 2), 'JSON')}>
            Copy JSON
          </button>
          <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300" type="button" disabled={busy} onClick={onExport}>
            Export Files
          </button>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {(['full', 'short', 'negative', 'json'] as PromptTab[]).map((item) => (
          <button
            className={`rounded-md px-3 py-2 text-xs font-semibold ${activeTab === item ? 'bg-blue-50 text-brand' : 'border border-line bg-white text-ink hover:border-brand'}`}
            key={item}
            type="button"
            onClick={() => onTab(item)}
          >
            {tabLabel(item)}
          </button>
        ))}
      </div>
      <pre className="mt-4 min-h-[420px] max-h-[720px] overflow-auto whitespace-pre-wrap rounded-md bg-surface p-4 text-xs leading-relaxed text-ink">
        {outputText || 'Chưa có prompt. Bấm Generate Prompt Pack để tạo storyboard và prompt.'}
      </pre>
      {Object.keys(files).length ? (
        <div className="mt-4 rounded-md border border-line bg-surface p-3 text-xs text-muted">
          <div className="mb-2 font-semibold text-ink">Exported files</div>
          <div className="space-y-1">
            {Object.entries(files).map(([key, value]) => (
              <div className="break-all" key={key}>
                <span className="font-semibold">{key}:</span> {value}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function promptTextForTab(promptPack: VideoPromptPack, tab: PromptTab): string {
  if (tab === 'short') return promptPack.short_prompt || '';
  if (tab === 'negative') return promptPack.negative_prompt;
  if (tab === 'json') return JSON.stringify(promptPack.json_prompt ?? promptPack, null, 2);
  return promptPack.video_prompt;
}

function tabLabel(tab: PromptTab): string {
  if (tab === 'full') return 'Full Prompt';
  if (tab === 'short') return 'Short Prompt';
  if (tab === 'negative') return 'Negative Prompt';
  return 'JSON';
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
      <span className="font-medium text-ink">{label}</span>
      <select
        className="h-10 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
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

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[150px_minmax(0,1fr)]">
      <span className="text-muted">{label}</span>
      <span className="break-all font-medium text-ink">{value}</span>
    </div>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-2 text-sm">
      <div className="font-semibold text-muted">{label}</div>
      <div className="whitespace-pre-wrap text-ink">{value || '-'}</div>
    </div>
  );
}
