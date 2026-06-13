import { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import GlassButton from '../glass/GlassButton';
import SettingsSection from './SettingsSection';
import { getStorageUsage, type StorageItem, type StorageUsageReport } from '../../services/dataManagementApi';
import { openFolder } from '../../services/localAppApi';
import { formatBytes } from '../../utils/formatBytes';

const categoryLabels: Record<string, string> = {
  config: 'Cài đặt',
  database: 'Database',
  projects: 'Dữ liệu Dự án',
  outputs: 'Outputs',
  exports: 'Gói xuất bản',
  subtitles: 'Phụ đề',
  logs: 'Logs',
  cache: 'Cache',
  temp: 'Temp',
  backups: 'Bản sao lưu (Backups)',
  frontend: 'Bản build giao diện',
};

export default function DataStorageUsageCard() {
  const [report, setReport] = useState<StorageUsageReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
  }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, StorageItem[]>();
    for (const item of report?.items ?? []) {
      map.set(item.category, [...(map.get(item.category) ?? []), item]);
    }
    return Array.from(map.entries());
  }, [report]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const response = await getStorageUsage();
      setReport(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải báo cáo dung lượng.');
    } finally {
      setLoading(false);
    }
  }

  async function openFirstOutputFolder() {
    const target = report?.items.find((item) => item.category === 'outputs' && item.exists)?.path;
    if (!target) return;
    try {
      await openFolder(target);
      setMessage('Đã mở thư mục outputs.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở thư mục outputs.');
    }
  }

  return (
    <SettingsSection
      title="Dung lượng Lưu trữ"
      description="Xem nhanh dung lượng app đang dùng. Các mục có thể cleanup vẫn cần preview trước khi xóa."
    >
      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
        <div className="rounded-md border border-white/10 bg-black/15 p-4">
          <div className="text-sm text-slate-400">Tổng dung lượng</div>
          <div className="mt-2 text-2xl font-semibold text-white">{formatBytes(report?.total_size_bytes ?? 0)}</div>
          <div className="mt-4 flex flex-wrap gap-2">
            <GlassButton loading={loading} onClick={() => void refresh()}>
              <RefreshCw size={16} /> Làm mới
            </GlassButton>
            <GlassButton variant="ghost" onClick={() => void openFirstOutputFolder()}>
              Mở thư mục output
            </GlassButton>
          </div>
        </div>
        <div className="grid gap-2">
          {grouped.map(([category, items]) => (
            <div key={category} className="rounded-md border border-white/10 bg-black/15 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold text-white">{categoryLabels[category] ?? category}</div>
                  <div className="text-xs text-slate-400">{items.filter((item) => item.exists).length}/{items.length} đường dẫn tồn tại</div>
                </div>
                <div className="font-mono text-sm text-cyan-100">{formatBytes(items.reduce((sum, item) => sum + item.size_bytes, 0))}</div>
              </div>
              <div className="mt-2 grid gap-1 text-xs text-slate-400">
                {items.slice(0, 3).map((item) => (
                  <div key={item.path} className="truncate">
                    {item.exists ? 'Tồn tại' : 'Thiếu'} · {item.description ?? item.path}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!report ? <div className="text-sm text-slate-400">Chưa có dữ liệu dung lượng.</div> : null}
        </div>
      </div>
      {error ? <div className="mt-3 rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100">{error}</div> : null}
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
    </SettingsSection>
  );
}

