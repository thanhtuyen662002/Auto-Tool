import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Clock, FolderOpen, Sparkles } from 'lucide-react';
import { createProject, getIndustryPresets, listProjects, updateProjectProductInfo } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassBadge from '../components/glass/GlassBadge';
import GlassButton from '../components/glass/GlassButton';
import GlassPagination from '../components/glass/GlassPagination';
import IndustryPresetSelector from '../components/industry/IndustryPresetSelector';
import NotifyOnChange from '../components/notifications/NotifyOnChange';
import ProductInfoImporter from '../components/productImport/ProductInfoImporter';
import ProductInfoForm from '../components/ProductInfoForm';
import type {
  ApplyIndustryPresetOptions,
  IndustryPreset,
  ProductInfoNormalized,
  ProjectConfig,
  ProjectListItem,
} from '../types/project';
import { getLocalAppConfig } from '../services/localAppApi';
import { applyIndustryPresetToConfig, DEFAULT_INDUSTRY_APPLY_OPTIONS } from '../utils/industryPresetApply';
import { getLocalUiSettings } from '../utils/localSettings';
import { defaultProjectConfig, saveProjectConfig } from '../utils/projectState';

const HISTORY_PAGE_SIZE = 5;

export default function CreateProjectPage() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<ProjectConfig>(() => projectConfigWithLocalPathDefaults());
  const [savedProjectId, setSavedProjectId] = useState<string | null>(null);
  const [lastSavedConfig, setLastSavedConfig] = useState<ProjectConfig | null>(null);
  const [industryPresets, setIndustryPresets] = useState<IndustryPreset[]>([]);
  const [industryApplyOptions, setIndustryApplyOptions] = useState<ApplyIndustryPresetOptions>(
    DEFAULT_INDUSTRY_APPLY_OPTIONS,
  );
  const [history, setHistory] = useState<ProjectListItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotalPages, setHistoryTotalPages] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedProjectId || !lastSavedConfig) return true;
    return JSON.stringify(config) !== JSON.stringify(lastSavedConfig);
  }, [config, lastSavedConfig, savedProjectId]);

  const selectedIndustry = useMemo(
    () => industryPresets.find((item) => item.id === (config.industry?.preset_id ?? 'general_product')) ?? null,
    [config.industry?.preset_id, industryPresets],
  );

  useEffect(() => {
    getIndustryPresets()
      .then((response) => setIndustryPresets(response.presets))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải danh sách ngành hàng.'));
  }, []);

  useEffect(() => {
    let active = true;
    const defaults = defaultProjectConfig();
    getLocalAppConfig()
      .then((localConfig) => {
        if (!active) return;
        setConfig((current) => ({
          ...current,
          source_folder: shouldApplyPathDefault(current.source_folder, defaults.source_folder)
            ? localConfig.default_source_folder || current.source_folder
            : current.source_folder,
          output_folder: shouldApplyPathDefault(current.output_folder, defaults.output_folder)
            ? localConfig.default_output_folder || current.output_folder
            : current.output_folder,
          music: {
            ...current.music,
            source_folder: shouldApplyPathDefault(current.music.source_folder || '', defaults.music.source_folder || '')
              ? localConfig.default_music_folder || current.music.source_folder
              : current.music.source_folder,
          },
        }));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    void loadHistory(historyPage);
  }, [historyPage]);

  async function loadHistory(page: number) {
    setHistoryLoading(true);
    try {
      const offset = (page - 1) * HISTORY_PAGE_SIZE;
      const response = await listProjects(HISTORY_PAGE_SIZE, offset, 'product_render');
      setHistory(response.items ?? []);
      setHistoryTotalPages(Math.max(1, Math.ceil((response.total || 0) / HISTORY_PAGE_SIZE)));
    } catch {
      setHistory([]);
      setHistoryTotalPages(1);
    } finally {
      setHistoryLoading(false);
    }
  }

  function handleIndustrySelect(presetId: string) {
    const preset = industryPresets.find((item) => item.id === presetId);
    if (!preset) return;
    setConfig((current) => applyIndustryPresetToConfig(current, preset, industryApplyOptions));
  }

  async function saveCurrentProject(): Promise<string> {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await createProject({ ...config, mode: 'product_render' });
      const nextConfig = { ...config, mode: 'product_render' };
      saveProjectConfig(response.project_id, nextConfig, false);
      setSavedProjectId(response.project_id);
      setLastSavedConfig(nextConfig);
      setConfig(nextConfig);
      setMessage('Đã lưu dự án Affiliate.');
      await loadHistory(historyPage);
      return response.project_id;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không thể lưu dự án.';
      setError(message);
      throw err;
    } finally {
      setSaving(false);
    }
  }

  async function handleSave() {
    try {
      await saveCurrentProject();
    } catch {
      // Error is rendered in ApiErrorBox.
    }
  }

  async function handleApplyImportedProduct(product: ProductInfoNormalized) {
    const localConfig: ProjectConfig = {
      ...config,
      product: {
        ...config.product,
        name: product.name,
        brand: product.brand ?? '',
        description: product.description,
        features: product.features,
        specs: product.specs,
        cta: product.cta,
        validation_warnings: product.warnings,
        hashtag_suggestions: product.hashtag_suggestions,
      },
      industry: product.industry_preset_id ? { preset_id: product.industry_preset_id } : config.industry,
    };

    if (!savedProjectId) {
      setConfig(localConfig);
      return;
    }

    const response = await updateProjectProductInfo(savedProjectId, product);
    const mergedConfig: ProjectConfig = {
      ...localConfig,
      product: response.updated_config.product,
      industry: response.updated_config.industry,
    };
    setConfig(mergedConfig);
    if (lastSavedConfig) {
      setLastSavedConfig({
        ...lastSavedConfig,
        product: response.updated_config.product,
        industry: response.updated_config.industry,
      });
    }
    saveProjectConfig(savedProjectId, mergedConfig, JSON.stringify(mergedConfig) !== JSON.stringify(lastSavedConfig));
  }

  async function handleContinue() {
    try {
      const projectId = savedProjectId && !isDirty ? savedProjectId : await saveCurrentProject();
      navigate(`/settings/${projectId}`);
    } catch {
      // Error is rendered in ApiErrorBox.
    }
  }

  return (
    <main className="studio-page grid max-w-full gap-6 overflow-x-hidden">
      <section className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <GlassBadge variant="ready">Video Affiliate</GlassBadge>
          <h1 className="mt-3 text-2xl font-semibold text-ink">Tạo Video Affiliate</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Nhập thông tin sản phẩm, chọn thư mục video nguồn và để tool tạo cấu hình render. Màn hình này chỉ hiển thị những gì cần thao tác, không còn JSON kỹ thuật.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/import-inbox">
            <GlassButton variant="secondary">
              <FolderOpen size={16} />
              Mở hộp thư sản phẩm
            </GlassButton>
          </Link>
          <Link to="/results">
            <GlassButton variant="ghost">Xem tác vụ đã chạy</GlassButton>
          </Link>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,380px)] 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <section className="glass-card-strong min-w-0 overflow-hidden p-5">
          <StepHeader step="1" title="Thông tin sản phẩm" description="Bạn có thể nhập tay hoặc dán mô tả để tool tự sắp xếp lại." />
          <div className="mt-4">
            <ProductInfoImporter industryPresets={industryPresets} onApply={handleApplyImportedProduct} />
          </div>

          <div className="mt-6">
            <StepHeader step="2" title="Cấu hình video" description="Điền thư mục nguồn, thư mục xuất và số lượng video muốn tạo." />
            <div className="mt-4">
              <ProductInfoForm config={config} onChange={setConfig} />
            </div>
          </div>

          <div className="mt-6 border-t border-line pt-5">
            <StepHeader step="3" title="Ngành hàng & phong cách" description="Chọn mẫu gần nhất với sản phẩm để tool gợi ý script, nhạc và visual phù hợp." />
            <div className="mt-4">
              <IndustryPresetSelector
                presets={industryPresets}
                selectedPresetId={config.industry?.preset_id ?? 'general_product'}
                applyOptions={industryApplyOptions}
                onApplyOptionsChange={setIndustryApplyOptions}
                onSelect={handleIndustrySelect}
              />
            </div>
          </div>

          <ApiErrorBox error={error} />
          <NotifyOnChange value={message} variant="success" />

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <GlassButton variant="secondary" loading={saving} onClick={handleSave}>
              Lưu dự án
            </GlassButton>
            <GlassButton variant="primary" loading={saving} onClick={handleContinue}>
              Tiếp tục tới cài đặt render
            </GlassButton>
            {savedProjectId ? (
              <span className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-200">
                Đã lưu dự án hiện tại
              </span>
            ) : null}
          </div>
        </section>

        <aside className="grid min-w-0 content-start gap-5">
          <AffiliatePreviewPanel config={config} industryName={selectedIndustry?.name ?? 'Chưa chọn ngành hàng'} isDirty={isDirty} />
          <AffiliateHistoryPanel
            projects={history}
            loading={historyLoading}
            currentPage={historyPage}
            totalPages={historyTotalPages}
            onPageChange={setHistoryPage}
          />
        </aside>
      </div>
    </main>
  );
}

function StepHeader({ step, title, description }: { step: string; title: string; description: string }) {
  return (
    <div className="flex min-w-0 gap-3">
      <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-sm font-semibold text-brand">
        {step}
      </div>
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted">{description}</p>
      </div>
    </div>
  );
}

function AffiliatePreviewPanel({
  config,
  industryName,
  isDirty,
}: {
  config: ProjectConfig;
  industryName: string;
  isDirty: boolean;
}) {
  const issues = previewIssues(config);
  const firstFeature = config.product.features.find((item) => item.trim())?.trim();
  const hook = firstFeature
    ? `Video sẽ mở đầu bằng lợi ích: ${firstFeature}.`
    : 'Video sẽ mở đầu bằng vấn đề của khách hàng và lợi ích chính của sản phẩm.';
  const hashtags = (config.product.hashtag_suggestions ?? []).slice(0, 5);
  const featurePreview = config.product.features.filter((item) => item.trim()).slice(0, 4);
  return (
    <section className="glass-card-strong min-w-0 overflow-hidden p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">Kết quả dự kiến</h2>
          <p className="mt-1 text-sm leading-6 text-muted">Bản tóm tắt dễ hiểu từ cài đặt hiện tại.</p>
        </div>
        <GlassBadge variant={issues.length ? 'warning' : isDirty ? 'neutral' : 'success'}>
          {issues.length ? 'Cần bổ sung' : isDirty ? 'Chưa lưu' : 'Đã sẵn sàng'}
        </GlassBadge>
      </div>

      <div className="mt-4 min-w-0 overflow-hidden rounded-md border border-line bg-surface p-4">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-brand">Preview video</div>
        <h3 className="mt-3 break-words text-xl font-semibold text-ink">{config.product.name || 'Tên sản phẩm sẽ hiển thị ở đây'}</h3>
        <p className="mt-2 break-words text-sm leading-6 text-muted">{config.product.description || 'Mô tả sản phẩm sẽ được dùng để viết lời bình và caption.'}</p>
        <div className="mt-3 break-words rounded-md border border-line bg-white/5 p-3 text-sm text-ink">{hook}</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {featurePreview.length ? featurePreview.map((item, index) => (
            <span key={`${item}-${index}`} className="max-w-full break-words rounded-full border border-line bg-white/5 px-3 py-1 text-xs text-muted">
              {item}
            </span>
          )) : (
            <span className="rounded-full border border-dashed border-line px-3 py-1 text-xs text-muted">
              Chưa có điểm nổi bật
            </span>
          )}
        </div>
      </div>

      <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2">
        <PreviewMetric label="Số video sẽ tạo" value={`${config.render.output_count || 0} video`} />
        <PreviewMetric label="Thời lượng mỗi video" value={`${config.render.duration || 0} giây`} />
        <PreviewMetric label="Khung hình" value={config.render.resolution || config.render.aspect_ratio || 'Chưa chọn'} />
        <PreviewMetric label="Ngành hàng" value={industryName} />
        <PreviewMetric label="Giọng đọc" value={config.tts?.provider ? friendlyProvider(config.tts.provider) : 'Theo cài đặt mặc định'} />
        <PreviewMetric label="Nhạc nền" value={config.music.enabled ? 'Có nhạc nền' : 'Không thêm nhạc'} />
      </div>

      <div className="mt-4 grid min-w-0 gap-2 text-sm">
        <PathLine label="Video nguồn" value={config.source_folder} />
        <PathLine label="Thư mục xuất" value={config.output_folder} />
      </div>

      {hashtags.length ? (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Hashtag gợi ý</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {hashtags.map((tag) => (
              <span key={tag} className="rounded-full border border-line bg-white/5 px-2.5 py-1 text-xs text-muted">{tag}</span>
            ))}
          </div>
        </div>
      ) : null}

      {issues.length ? (
        <div className="mt-4 rounded-md border border-amber-300/30 bg-amber-300/10 p-3 text-sm text-amber-200">
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <AlertTriangle size={16} />
            Cần bổ sung trước khi render
          </div>
          <ul className="space-y-1">
            {issues.map((issue) => <li key={issue}>- {issue}</li>)}
          </ul>
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-2 rounded-md border border-emerald-300/30 bg-emerald-300/10 p-3 text-sm text-emerald-200">
          <CheckCircle2 size={16} />
          Cấu hình cơ bản đã đủ để chuyển sang bước cài đặt render.
        </div>
      )}
    </section>
  );
}

function AffiliateHistoryPanel({
  projects,
  loading,
  currentPage,
  totalPages,
  onPageChange,
}: {
  projects: ProjectListItem[];
  loading: boolean;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <section className="glass-card-strong min-w-0 overflow-hidden p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">Lịch sử Affiliate</h2>
          <p className="mt-1 text-sm leading-6 text-muted">Mở lại những dự án sản phẩm đã tạo gần đây.</p>
        </div>
        <GlassBadge variant="neutral">{projects.length} mục</GlassBadge>
      </div>

      <div className="mt-4 grid min-w-0 gap-3">
        {loading ? (
          <div className="rounded-md border border-line bg-surface p-4 text-sm text-muted">Đang tải lịch sử...</div>
        ) : projects.length ? (
          projects.map((project) => (
            <div key={project.id} className="min-w-0 rounded-md border border-line bg-surface p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-semibold text-ink">{project.project_name}</div>
                  <div className="mt-1 truncate text-xs text-muted">{project.product_name || 'Chưa có tên sản phẩm'}</div>
                </div>
                <span className="shrink-0 rounded-full border border-purple-300/30 bg-purple-300/10 px-2 py-1 text-[11px] font-semibold text-purple-200">
                  Affiliate
                </span>
              </div>
              <div className="mt-3 grid gap-1 text-xs text-muted">
                <span className="flex items-center gap-1"><Clock size={12} /> {formatDate(project.created_at)}</span>
                <span className="truncate">Xuất: {project.output_folder || 'Chưa rõ'}</span>
                <span>{project.output_count ?? 0} video dự kiến</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link to={`/settings/${project.id}`}>
                  <GlassButton variant="secondary" className="min-h-8 px-3 text-xs">Mở cài đặt</GlassButton>
                </Link>
                <Link to={`/projects/${project.id}/source-media`}>
                  <GlassButton variant="ghost" className="min-h-8 px-3 text-xs">Xem video nguồn</GlassButton>
                </Link>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-line bg-surface p-5 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-muted" />
            <div className="mt-3 font-semibold text-ink">Chưa có dự án Affiliate</div>
            <p className="mt-1 text-sm text-muted">Sau khi lưu dự án, lịch sử sẽ xuất hiện ở đây.</p>
          </div>
        )}
      </div>

      {totalPages > 1 ? (
        <GlassPagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} className="mt-4" />
      ) : null}
    </section>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

function PathLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-line bg-surface px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 truncate text-sm text-ink">{value || 'Chưa chọn'}</div>
    </div>
  );
}

function previewIssues(config: ProjectConfig): string[] {
  const issues: string[] = [];
  if (!config.project_name.trim()) issues.push('Nhập tên dự án để dễ tìm lại trong lịch sử.');
  if (!config.product.name.trim()) issues.push('Nhập tên sản phẩm.');
  if (!config.product.description.trim() && !config.product.features.some((item) => item.trim())) {
    issues.push('Thêm mô tả hoặc điểm nổi bật để tool viết lời bình.');
  }
  if (!config.source_folder.trim()) issues.push('Chọn thư mục video nguồn.');
  if (!config.output_folder.trim()) issues.push('Chọn thư mục đầu ra.');
  if (!config.product.cta.trim()) issues.push('Thêm lời kêu gọi hành động, ví dụ: Xem chi tiết ngay.');
  return issues;
}

function friendlyProvider(provider: string): string {
  const normalized = provider.toLowerCase();
  if (normalized.includes('google')) return 'Google Cloud TTS';
  if (normalized.includes('piper')) return 'Piper offline';
  return provider;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN');
}

function projectConfigWithLocalPathDefaults(): ProjectConfig {
  const base = defaultProjectConfig();
  const local = getLocalUiSettings();
  return {
    ...base,
    mode: 'product_render',
    project_name: '',
    source_folder: local.defaultSourceFolder || '',
    output_folder: local.defaultOutputFolder || '',
    product: {
      ...base.product,
      name: '',
      brand: '',
      description: '',
      features: [''],
      specs: [],
      cta: '',
      validation_warnings: [],
      hashtag_suggestions: [],
    },
    music: {
      ...base.music,
      source_folder: local.defaultMusicFolder || '',
    },
  };
}

function shouldApplyPathDefault(current: string, originalDefault: string): boolean {
  return !current.trim() || current === originalDefault;
}
