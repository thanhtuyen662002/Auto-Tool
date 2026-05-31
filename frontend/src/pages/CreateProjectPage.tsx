import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createProject } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import ProductInfoForm from '../components/ProductInfoForm';
import type { ProjectConfig } from '../types/project';
import { defaultProjectConfig, formatJson, maskSensitiveConfig, saveProjectConfig } from '../utils/projectState';

export default function CreateProjectPage() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<ProjectConfig>(() => defaultProjectConfig());
  const [savedProjectId, setSavedProjectId] = useState<string | null>(null);
  const [lastSavedConfig, setLastSavedConfig] = useState<ProjectConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const isDirty = useMemo(() => {
    if (!savedProjectId || !lastSavedConfig) return true;
    return JSON.stringify(config) !== JSON.stringify(lastSavedConfig);
  }, [config, lastSavedConfig, savedProjectId]);

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
        <h1 className="text-2xl font-semibold text-ink">Tạo dự án</h1>
          <p className="mt-1 text-sm text-muted">Nhập thông tin sản phẩm và thư mục trên máy để tạo cấu hình render.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <ProductInfoForm config={config} onChange={setConfig} />

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
