import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createProject, getIndustryPresets, updateProjectProductInfo } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import IndustryPresetSelector from '../components/industry/IndustryPresetSelector';
import ProductInfoImporter from '../components/productImport/ProductInfoImporter';
import ProductInfoForm from '../components/ProductInfoForm';
import type { ApplyIndustryPresetOptions, IndustryPreset, ProductInfoNormalized, ProjectConfig } from '../types/project';
import { applyIndustryPresetToConfig, DEFAULT_INDUSTRY_APPLY_OPTIONS } from '../utils/industryPresetApply';
import { defaultProjectConfig, formatJson, maskSensitiveConfig, saveProjectConfig } from '../utils/projectState';

export default function CreateProjectPage() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<ProjectConfig>(() => defaultProjectConfig());
  const [savedProjectId, setSavedProjectId] = useState<string | null>(null);
  const [lastSavedConfig, setLastSavedConfig] = useState<ProjectConfig | null>(null);
  const [industryPresets, setIndustryPresets] = useState<IndustryPreset[]>([]);
  const [industryApplyOptions, setIndustryApplyOptions] = useState<ApplyIndustryPresetOptions>(
    DEFAULT_INDUSTRY_APPLY_OPTIONS,
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedProjectId || !lastSavedConfig) return true;
    return JSON.stringify(config) !== JSON.stringify(lastSavedConfig);
  }, [config, lastSavedConfig, savedProjectId]);

  useEffect(() => {
    getIndustryPresets()
      .then((response) => setIndustryPresets(response.presets))
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải danh sách ngành hàng.'));
  }, []);

  function handleIndustrySelect(presetId: string) {
    const preset = industryPresets.find((item) => item.id === presetId);
    if (!preset) return;
    setConfig((current) => applyIndustryPresetToConfig(current, preset, industryApplyOptions));
  }

  async function saveCurrentProject(): Promise<string> {
    setSaving(true);
    setError(null);
    try {
      const response = await createProject(config);
      saveProjectConfig(response.project_id, config, false);
      setSavedProjectId(response.project_id);
      setLastSavedConfig(config);
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
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5">
        <button
          className="mb-3 rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
          type="button"
          onClick={() => navigate('/import-inbox')}
        >
          Open Import Inbox
        </button>
        <h1 className="text-2xl font-semibold text-ink">Tạo dự án</h1>
          <p className="mt-1 text-sm text-muted">Nhập thông tin sản phẩm và thư mục trên máy để tạo cấu hình render.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="mb-6">
            <ProductInfoImporter industryPresets={industryPresets} onApply={handleApplyImportedProduct} />
          </div>

          <ProductInfoForm config={config} onChange={setConfig} />

          <div className="mt-6 border-t border-line pt-5">
            <IndustryPresetSelector
              presets={industryPresets}
              selectedPresetId={config.industry?.preset_id ?? 'general_product'}
              applyOptions={industryApplyOptions}
              onApplyOptionsChange={setIndustryApplyOptions}
              onSelect={handleIndustrySelect}
            />
          </div>

          <ApiErrorBox error={error} />

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:hover:border-line"
              type="button"
              disabled={saving}
              onClick={handleSave}
            >
              {saving ? 'Đang lưu...' : 'Lưu dự án'}
            </button>
            <button
              className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              type="button"
              disabled={saving}
              onClick={handleContinue}
            >
              Tiếp tục tới cài đặt
            </button>
            {savedProjectId ? (
              <span className="text-xs text-muted">
                Dự án đã lưu: <span className="font-mono">{savedProjectId}</span>
              </span>
            ) : null}
          </div>
        </section>

        <aside className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-ink">Xem trước cấu hình</h2>
            <span className="rounded bg-surface px-2 py-1 text-xs text-muted">{isDirty ? 'chưa lưu' : 'đã lưu'}</span>
          </div>
          <pre className="max-h-[720px] overflow-auto rounded-md bg-surface p-4 text-xs leading-relaxed text-ink">
            {formatJson(maskSensitiveConfig(config))}
          </pre>
        </aside>
      </div>
    </main>
  );
}
