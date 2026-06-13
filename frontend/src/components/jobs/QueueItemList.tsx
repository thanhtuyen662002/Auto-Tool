import { CheckCircle2, Circle, CircleAlert, Clock, Loader2 } from 'lucide-react';
import type { QueueItem, QueueState } from '../../types/project';

interface QueueItemListProps {
  queue: QueueState | null;
  selectedIds: Set<string>;
  onToggle: (itemId: string) => void;
  onSelectAllQueued: () => void;
  onClearSelection: () => void;
}

export default function QueueItemList({
  queue,
  selectedIds,
  onToggle,
  onSelectAllQueued,
  onClearSelection,
}: QueueItemListProps) {
  const items = queue?.items ?? [];

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Danh sách video</h2>
          <p className="mt-1 text-sm text-muted">{items.length ? `${selectedIds.size} video đang được chọn` : 'Chưa có dữ liệu hàng đợi.'}</p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:bg-surface" onClick={onSelectAllQueued}>
            Chọn item chờ/lỗi
          </button>
          <button type="button" className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:bg-surface" onClick={onClearSelection}>
            Bỏ chọn
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-line">
        {items.length ? (
          items
            .slice()
            .sort((a, b) => a.order_index - b.order_index)
            .map((item) => (
              <QueueRow
                key={item.id}
                item={item}
                selected={selectedIds.has(item.id)}
                onToggle={() => onToggle(item.id)}
              />
            ))
        ) : (
          <div className="p-4 text-sm text-muted">Queue state sẽ xuất hiện sau khi worker bắt đầu xử lý job.</div>
        )}
      </div>
    </section>
  );
}

function QueueRow({ item, selected, onToggle }: { item: QueueItem; selected: boolean; onToggle: () => void }) {
  const canSelect = !['running', 'completed', 'rendered'].includes(item.status);
  return (
    <div className="grid gap-3 border-b border-line p-3 last:border-b-0 md:grid-cols-[32px_1fr_130px_90px]">
      <label className="flex items-start pt-1">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-line"
          checked={selected}
          disabled={!canSelect}
          onChange={onToggle}
          aria-label={`Chọn ${item.filename ?? item.video_id}`}
        />
      </label>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <StatusIcon status={item.status} />
          <span className="truncate">{item.filename || item.video_id}</span>
        </div>
        <div className="mt-1 truncate text-xs text-muted">{item.video_path}</div>
        {item.output_video_path ? <div className="mt-1 truncate text-xs text-emerald-700">{item.output_video_path}</div> : null}
        {item.error_message ? <div className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">{item.error_message}</div> : null}
      </div>
      <div className="text-sm">
        <div className="font-semibold text-ink">{statusLabel(item.status)}</div>
        <div className="mt-1 text-xs text-muted">{item.current_step || 'Chưa chạy'}</div>
      </div>
      <div className="text-sm">
        <div className="font-semibold text-ink">{Math.round(item.progress_percent || 0)}%</div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface">
          <div className="h-full bg-brand" style={{ width: `${Math.max(0, Math.min(100, item.progress_percent || 0))}%` }} />
        </div>
      </div>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'running') return <Loader2 size={16} className="animate-spin text-brand" />;
  if (['completed', 'rendered'].includes(status)) return <CheckCircle2 size={16} className="text-emerald-600" />;
  if (status === 'failed') return <CircleAlert size={16} className="text-rose-600" />;
  if (status === 'queued') return <Clock size={16} className="text-muted" />;
  return <Circle size={16} className="text-muted" />;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    running: 'Đang chạy',
    paused: 'Tạm dừng',
    completed: 'Hoàn thành',
    rendered: 'Đã render',
    failed: 'Lỗi',
    skipped: 'Bỏ qua',
    cancelled: 'Đã hủy',
    needs_review: 'Cần xem lại',
  };
  return labels[status] ?? status;
}
