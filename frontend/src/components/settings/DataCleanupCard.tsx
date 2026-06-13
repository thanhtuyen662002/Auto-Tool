import { useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassInput from '../glass/GlassInput';
import SettingsSection from './SettingsSection';
import {
  previewCleanup,
  runCleanup,
  type CleanupRequest,
  type CleanupResult,
  type CleanupTarget,
} from '../../services/dataManagementApi';
import { formatBytes } from '../../utils/formatBytes';

const targets: Array<{ id: CleanupTarget; label: string; defaultChecked: boolean }> = [
  { id: 'launcher_logs', label: 'Launcher logs cũ', defaultChecked: true },
  { id: 'debug_logs', label: 'Debug logs cũ', defaultChecked: true },
  { id: 'temp_files', label: 'Tệp tạm thời (Temp)', defaultChecked: true },
  { id: 'cache_files', label: 'Tệp đệm (Cache)', defaultChecked: true },
  { id: 'preview_frames', label: 'Khung hình xem trước (Preview)', defaultChecked: true },
  { id: 'failed_partial_renders', label: 'Các phần render lỗi', defaultChecked: false },
  { id: 'old_exports', label: 'Gói xuất bản cũ', defaultChecked: false },
];

export default function DataCleanupCard() {
  const [selected, setSelected] = useState<CleanupTarget[]>(targets.filter((item) => item.defaultChecked).map((item) => item.id));
  const [olderThanDays, setOlderThanDays] = useState(14);
  const [preview, setPreview] = useState<CleanupResult | null>(null);
  const [result, setResult] = useState<CleanupResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totals = useMemo(() => {
    const items = preview?.preview_items ?? [];
    return {
      files: items.reduce((sum, item) => sum + item.file_count, 0),
      size: items.reduce((sum, item) => sum + item.size_bytes, 0),
    };
  }, [preview]);

  async function handlePreview() {
    setLoading(true);
    setError(null);
    setResult(null);
    setConfirmed(false);
    try {
      setPreview(await previewCleanup(buildRequest(true, false)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể preview cleanup.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRun() {
    if (!preview || !confirmed) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await runCleanup(buildRequest(false, true)));
      setConfirmed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể chạy cleanup.');
    } finally {
      setLoading(false);
    }
  }

  function buildRequest(dryRun: boolean, confirmDelete: boolean): CleanupRequest {
    return {
      targets: selected,
      older_than_days: olderThanDays,
      dry_run: dryRun,
      confirm_delete: confirmDelete,
    };
  }

  return (
    <SettingsSection title="Dọn dẹp Bộ nhớ" description="Cleanup luôn bắt đầu bằng preview. Không xóa source videos, music folder, database hoặc config.">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="grid gap-3">
          <div className="grid gap-2 md:grid-cols-2">
            {targets.map((target) => (
              <label key={target.id} className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-200">
                <input
                  className="h-4 w-4"
                  type="checkbox"
                  checked={selected.includes(target.id)}
                  onChange={(event) => setSelected((current) => event.target.checked ? [...current, target.id] : current.filter((item) => item !== target.id))}
                />
                <span>{target.label}</span>
              </label>
            ))}
          </div>
          <GlassInput
            label="Số ngày cũ hơn"
            type="number"
            min={0}
            value={olderThanDays}
            onChange={(event) => setOlderThanDays(Math.max(0, Number(event.target.value) || 0))}
          />
          <div className="flex flex-wrap gap-2">
            <GlassButton loading={loading} onClick={() => void handlePreview()}>Xem trước dọn dẹp</GlassButton>
            <GlassButton variant="danger" loading={loading} disabled={!preview || !confirmed} onClick={() => void handleRun()}>
              Chạy dọn dẹp
            </GlassButton>
          </div>
          <label className="flex items-start gap-3 rounded-md border border-amber-400/25 bg-amber-400/10 p-3 text-sm text-amber-100">
            <input className="mt-1 h-4 w-4" type="checkbox" checked={confirmed} disabled={!preview} onChange={(event) => setConfirmed(event.target.checked)} />
            <span>Tôi hiểu thao tác này sẽ xóa các file đã liệt kê trong preview.</span>
          </label>
          {error ? <div className="rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100">{error}</div> : null}
        </div>
        <div className="rounded-md border border-white/10 bg-black/15 p-4 text-sm text-slate-300">
          <h3 className="font-semibold text-white">Xem trước dọn dẹp</h3>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Metric label="Số tệp" value={String(totals.files)} />
            <Metric label="Dung lượng" value={formatBytes(totals.size)} />
          </div>
          {preview ? (
            <div className="mt-3">
              {preview.warnings.map((item) => <div key={item} className="text-amber-200">Cảnh báo: {item}</div>)}
              {preview.errors.map((item) => <div key={item} className="text-rose-200">Lỗi: {item}</div>)}
              <GlassButton className="mt-3" variant="ghost" onClick={() => setShowDetails((value) => !value)}>
                {showDetails ? 'Ẩn chi tiết' : 'Hiện chi tiết'}
              </GlassButton>
              {showDetails ? (
                <div className="mt-3 max-h-72 overflow-auto rounded-md border border-white/10 bg-slate-950/50 p-2">
                  {preview.preview_items.slice(0, 200).map((item) => (
                    <div key={item.path} className="border-b border-white/5 py-2 last:border-b-0">
                      <div className="break-all font-mono text-xs text-slate-100">{item.path}</div>
                      <div className="text-xs text-slate-400">{item.reason} · {formatBytes(item.size_bytes)} · {item.file_count} file</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : <div className="mt-3 text-slate-400">Bấm Xem trước dọn dẹp để xem danh sách file trước.</div>}
          {result ? (
            <div className="mt-3 rounded-md border border-emerald-400/25 bg-emerald-400/10 p-3 text-emerald-100">
              Đã xóa {result.deleted_file_count} file, {formatBytes(result.deleted_size_bytes)}.
            </div>
          ) : null}
        </div>
      </div>
    </SettingsSection>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-950/40 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="font-semibold text-white">{value}</div>
    </div>
  );
}

