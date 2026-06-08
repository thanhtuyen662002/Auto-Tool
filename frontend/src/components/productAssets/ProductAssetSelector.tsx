import { useEffect, useMemo, useState } from 'react';
import {
  importProductDraftAssets,
  listProductDraftAssets,
  productAssetFileUrl,
  updateProductAsset,
} from '../../api/client';
import type { ProductAsset, ProductAssetRole } from '../../types/project';

const ROLES: Array<{ value: ProductAssetRole; label: string }> = [
  { value: 'main_product', label: 'Main Product' },
  { value: 'reference', label: 'Reference' },
  { value: 'poster', label: 'Poster' },
  { value: 'thumbnail', label: 'Thumbnail' },
  { value: 'description', label: 'Description' },
  { value: 'variation', label: 'Variation' },
  { value: 'unused', label: 'Unused' },
];

export default function ProductAssetSelector({
  draftId,
  onSelectionChange,
}: {
  draftId: string;
  onSelectionChange?: (assetIds: string[]) => void;
}) {
  const [assets, setAssets] = useState<ProductAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const selectedAssetIds = useMemo(
    () => assets.filter((asset) => asset.is_selected && asset.status !== 'skipped').map((asset) => asset.id),
    [assets],
  );

  useEffect(() => {
    void loadAssets();
  }, [draftId]);

  useEffect(() => {
    onSelectionChange?.(selectedAssetIds);
  }, [onSelectionChange, selectedAssetIds]);

  async function loadAssets() {
    setLoading(true);
    setError(null);
    try {
      const response = await listProductDraftAssets(draftId);
      setAssets(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tải được danh sách ảnh sản phẩm.');
    } finally {
      setLoading(false);
    }
  }

  async function importSelected() {
    const selectedUrls = assets.filter((asset) => asset.is_selected && asset.original_url).map((asset) => asset.original_url!);
    if (!selectedUrls.length) {
      setError('Hãy chọn ít nhất một ảnh trước khi import.');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const response = await importProductDraftAssets(draftId, {
        selected_asset_urls: selectedUrls,
        download_selected: true,
      });
      setAssets(response.items);
      setMessage('Đã import ảnh đã chọn.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import assets thất bại.');
    } finally {
      setBusy(false);
    }
  }

  async function updateAsset(assetId: string, payload: { role?: ProductAssetRole; is_selected?: boolean }) {
    setBusy(true);
    setError(null);
    try {
      const response = await updateProductAsset(assetId, payload);
      const updated = response.items[0];
      setAssets((current) => current.map((asset) => (asset.id === assetId ? updated : asset)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không cập nhật được asset.');
    } finally {
      setBusy(false);
    }
  }

  async function setMainProduct(assetId: string) {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không đặt được ảnh chính.');
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
        <h3 className="text-base font-semibold text-ink">Product Assets</h3>
        <p className="mt-2 text-sm text-muted">Đang tải ảnh từ draft...</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-ink">Product Assets</h3>
          <p className="mt-1 text-sm text-muted">Ảnh được lấy từ Shopee draft. Chỉ ảnh được chọn mới được lưu local.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            disabled={busy}
            onClick={() => void loadAssets()}
          >
            Refresh
          </button>
          <button
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            type="button"
            disabled={busy || !selectedAssetIds.length}
            onClick={() => void importSelected()}
          >
            {busy ? 'Đang xử lý...' : 'Import Assets'}
          </button>
        </div>
      </div>

      {error ? <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      {message ? <p className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">{message}</p> : null}

      {!assets.length ? (
        <p className="mt-4 text-sm text-muted">Draft này chưa có image URL để import.</p>
      ) : (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {assets.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              busy={busy}
              onToggle={(selected) => void updateAsset(asset.id, { is_selected: selected })}
              onRole={(role) => void updateAsset(asset.id, { role })}
              onSetMain={() => void setMainProduct(asset.id)}
              onSkip={() => void updateAsset(asset.id, { role: 'unused', is_selected: false })}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function AssetCard({
  asset,
  busy,
  onToggle,
  onRole,
  onSetMain,
  onSkip,
}: {
  asset: ProductAsset;
  busy: boolean;
  onToggle: (selected: boolean) => void;
  onRole: (role: ProductAssetRole) => void;
  onSetMain: () => void;
  onSkip: () => void;
}) {
  const previewUrl = asset.local_path ? productAssetFileUrl(asset.id) : asset.original_url || '';
  const quality = asset.quality_score == null ? 'N/A' : `${Math.round(asset.quality_score * 100)}%`;
  return (
    <article className="overflow-hidden rounded-lg border border-line bg-surface/50">
      <div className="aspect-square bg-white">
        {previewUrl ? (
          <img className="h-full w-full object-contain" src={previewUrl} alt={asset.filename || 'Product asset'} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted">No preview</div>
        )}
      </div>
      <div className="space-y-3 p-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Info label="Role" value={roleLabel(asset.role)} />
          <Info label="Status" value={asset.status} />
          <Info label="Quality" value={quality} />
          <Info label="Size" value={asset.width && asset.height ? `${asset.width}x${asset.height}` : 'N/A'} />
        </div>

        <label className="flex items-center gap-2 text-sm text-ink">
          <input checked={asset.is_selected} disabled={busy} type="checkbox" onChange={(event) => onToggle(event.target.checked)} />
          Select
        </label>

        <select
          className="w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
          disabled={busy}
          value={asset.role}
          onChange={(event) => onRole(event.target.value as ProductAssetRole)}
        >
          {ROLES.map((role) => (
            <option key={role.value} value={role.value}>
              {role.label}
            </option>
          ))}
        </select>

        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white disabled:opacity-60" type="button" disabled={busy} onClick={onSetMain}>
            Set as Main
          </button>
          <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" disabled={busy} onClick={onSkip}>
            Skip
          </button>
        </div>

        {asset.errors.length ? <p className="text-xs text-red-700">{asset.errors[0]}</p> : null}
        {asset.warnings.length ? <p className="text-xs text-amber-700">{asset.warnings[0]}</p> : null}
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

function roleLabel(role: ProductAssetRole): string {
  return ROLES.find((item) => item.value === role)?.label ?? role;
}
