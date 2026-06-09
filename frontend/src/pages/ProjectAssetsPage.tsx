import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  deleteProductAsset,
  getProject,
  listProjectAssets,
  productAssetFileUrl,
  updateProductAsset,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import type { ProductAsset, ProductAssetRole, ProjectConfig } from '../types/project';

const ROLE_GROUPS: ProductAssetRole[] = ['main_product', 'reference', 'poster', 'thumbnail', 'description', 'variation', 'unused'];

export default function ProjectAssetsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [assets, setAssets] = useState<ProductAsset[]>([]);
  const [config, setConfig] = useState<ProjectConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const byRole = new Map<ProductAssetRole, ProductAsset[]>();
    for (const role of ROLE_GROUPS) byRole.set(role, []);
    for (const asset of assets) {
      byRole.get(asset.role)?.push(asset);
    }
    return byRole;
  }, [assets]);

  useEffect(() => {
    if (projectId) void load(projectId);
  }, [projectId]);

  async function load(activeProjectId: string) {
    setLoading(true);
    setError(null);
    try {
      const [project, response] = await Promise.all([getProject(activeProjectId), listProjectAssets(activeProjectId)]);
      setConfig(project.config);
      setAssets(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được product assets.');
    } finally {
      setLoading(false);
    }
  }

  async function updateAsset(assetId: string, payload: { role?: ProductAssetRole; is_selected?: boolean }) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await updateProductAsset(assetId, payload);
      const updated = response.items[0];
      setAssets((current) => current.map((asset) => (asset.id === assetId ? updated : asset)));
      setMessage('Đã cập nhật asset.');
      if (projectId) {
        const project = await getProject(projectId);
        setConfig(project.config);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không cập nhật được asset.');
    } finally {
      setBusy(false);
    }
  }

  async function setMain(assetId: string) {
    setBusy(true);
    setError(null);
    try {
      const nextAssets: ProductAsset[] = [];
      for (const asset of assets) {
        const role: ProductAssetRole = asset.id === assetId ? 'main_product' : asset.role === 'main_product' ? 'reference' : asset.role;
        const response = await updateProductAsset(asset.id, {
          role,
          is_selected: asset.id === assetId ? true : asset.is_selected,
        });
        nextAssets.push(response.items[0]);
      }
      setAssets(nextAssets);
      if (projectId) {
        const project = await getProject(projectId);
        setConfig(project.config);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đặt được ảnh chính.');
    } finally {
      setBusy(false);
    }
  }

  async function removeAsset(assetId: string) {
    if (!window.confirm('Remove asset from project? File local sẽ được giữ lại.')) return;
    setBusy(true);
    setError(null);
    try {
      const response = await deleteProductAsset(assetId);
      const updated = response.items[0];
      setAssets((current) => current.map((asset) => (asset.id === assetId ? updated : asset)));
      setMessage('Đã remove asset khỏi project.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không remove được asset.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Product Assets</h1>
          <p className="mt-1 text-sm text-muted">
            {config ? config.project_name : projectId} · Main asset: {config?.assets?.main_product_asset_id ?? 'N/A'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
            type="button"
            disabled={!projectId}
            onClick={() => navigate(projectId ? `/projects/${projectId}/prompt-pack` : '/')}
          >
            Use for Prompt Pack
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            onClick={() => navigate(projectId ? `/settings/${projectId}` : '/')}
          >
            Back to Settings
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            disabled={!projectId || busy}
            onClick={() => projectId && void load(projectId)}
          >
            Refresh
          </button>
        </div>
      </div>

      <ApiErrorBox error={error} />
      {message ? <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{message}</div> : null}

      {loading ? <p className="rounded-lg border border-line bg-white p-5 text-sm text-muted">Đang tải assets...</p> : null}
      {!loading && assets.length === 0 ? (
        <p className="rounded-lg border border-line bg-white p-5 text-sm text-muted">Project chưa có product assets.</p>
      ) : null}

      <div className="space-y-6">
        {ROLE_GROUPS.map((role) => {
          const items = grouped.get(role) ?? [];
          if (!items.length) return null;
          return (
            <section className="rounded-lg border border-line bg-white p-5 shadow-panel" key={role}>
              <h2 className="text-base font-semibold text-ink">{roleTitle(role)}</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    busy={busy}
                    onSetMain={() => void setMain(asset.id)}
                    onRole={(nextRole) => void updateAsset(asset.id, { role: nextRole })}
                    onRemove={() => void removeAsset(asset.id)}
                    onCopy={() => {
                      void navigator.clipboard.writeText(asset.local_path || asset.original_url || '');
                      setMessage('Đã copy path.');
                    }}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </main>
  );
}

function AssetCard({
  asset,
  busy,
  onSetMain,
  onRole,
  onRemove,
  onCopy,
}: {
  asset: ProductAsset;
  busy: boolean;
  onSetMain: () => void;
  onRole: (role: ProductAssetRole) => void;
  onRemove: () => void;
  onCopy: () => void;
}) {
  const previewUrl = asset.local_path ? productAssetFileUrl(asset.id) : asset.original_url || '';
  return (
    <article className="overflow-hidden rounded-lg border border-line bg-surface/40">
      <div className="aspect-square bg-white">
        {previewUrl ? <img className="h-full w-full object-contain" src={previewUrl} alt={asset.filename || 'Product asset'} /> : null}
      </div>
      <div className="space-y-3 p-3">
        <div className="text-sm font-semibold text-ink">{asset.filename || 'Remote asset'}</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Info label="Status" value={asset.status} />
          <Info label="Quality" value={asset.quality_score == null ? 'N/A' : `${Math.round(asset.quality_score * 100)}%`} />
          <Info label="Size" value={asset.width && asset.height ? `${asset.width}x${asset.height}` : 'N/A'} />
          <Info label="Selected" value={asset.is_selected ? 'Yes' : 'No'} />
        </div>
        <select
          className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
          disabled={busy}
          value={asset.role}
          onChange={(event) => onRole(event.target.value as ProductAssetRole)}
        >
          {ROLE_GROUPS.map((role) => (
            <option key={role} value={role}>
              {roleTitle(role)}
            </option>
          ))}
        </select>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:opacity-60" type="button" disabled={busy} onClick={onSetMain}>
            Set Main
          </button>
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" disabled={busy} onClick={onCopy}>
            Copy Path
          </button>
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-red-600 hover:border-red-400" type="button" disabled={busy} onClick={onRemove}>
            Remove
          </button>
        </div>
        {asset.errors.length ? <p className="text-xs text-red-700">{asset.errors[0]}</p> : null}
      </div>
    </article>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-semibold text-muted">{label}</div>
      <div className="truncate text-ink">{value}</div>
    </div>
  );
}

function roleTitle(role: ProductAssetRole): string {
  return role
    .split('_')
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(' ');
}
