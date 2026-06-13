import { ArrowDown, ArrowUp, Pause, Play, RotateCcw, SkipForward, XCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import type { QueueActionResult, QueueState } from '../../types/project';

interface QueueControlPanelProps {
  queue: QueueState | null;
  selectedCount: number;
  busyAction: string | null;
  actionMessage: string | null;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onRetryFailed: () => void;
  onRetrySelected: () => void;
  onSkipSelected: () => void;
  onPrioritizeSelected: () => void;
  onMoveToTop: () => void;
  onMoveToBottom: () => void;
  lastResult?: QueueActionResult | null;
}

export default function QueueControlPanel({
  queue,
  selectedCount,
  busyAction,
  actionMessage,
  onPause,
  onResume,
  onCancel,
  onRetryFailed,
  onRetrySelected,
  onSkipSelected,
  onPrioritizeSelected,
  onMoveToTop,
  onMoveToBottom,
}: QueueControlPanelProps) {
  const status = queue?.status ?? 'queued';
  const hasSelection = selectedCount > 0;
  const disabled = Boolean(busyAction);

  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Điều khiển hàng đợi</h2>
          <p className="mt-1 text-sm text-muted">
            Trạng thái: <span className="font-semibold text-ink">{statusLabel(status)}</span>
            {queue ? ` · ${queue.completed_items}/${queue.total_items} video đã xong` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ActionButton icon={<Pause size={16} />} label="Tạm dừng" busy={busyAction === 'pause'} disabled={disabled || status === 'paused'} onClick={onPause} />
          <ActionButton icon={<Play size={16} />} label="Tiếp tục" busy={busyAction === 'resume'} disabled={disabled} onClick={onResume} />
          <ActionButton icon={<XCircle size={16} />} label="Hủy batch" busy={busyAction === 'cancel'} disabled={disabled || status === 'cancelled'} danger onClick={onCancel} />
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-5">
        <Metric label="Đang chờ" value={queue?.queued_items ?? 0} />
        <Metric label="Đang chạy" value={queue?.running_items ?? 0} />
        <Metric label="Cần xem lại" value={queue?.needs_review_items ?? 0} />
        <Metric label="Lỗi" value={queue?.failed_items ?? 0} danger />
        <Metric label="Bỏ qua" value={queue?.skipped_items ?? 0} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton icon={<RotateCcw size={16} />} label="Retry lỗi" busy={busyAction === 'retryFailed'} disabled={disabled || !queue?.failed_items} onClick={onRetryFailed} />
        <ActionButton icon={<RotateCcw size={16} />} label={`Retry đã chọn (${selectedCount})`} busy={busyAction === 'retrySelected'} disabled={disabled || !hasSelection} onClick={onRetrySelected} />
        <ActionButton icon={<SkipForward size={16} />} label="Bỏ qua đã chọn" busy={busyAction === 'skipSelected'} disabled={disabled || !hasSelection} onClick={onSkipSelected} />
        <ActionButton icon={<ArrowUp size={16} />} label="Ưu tiên" busy={busyAction === 'prioritize'} disabled={disabled || !hasSelection} onClick={onPrioritizeSelected} />
        <ActionButton icon={<ArrowUp size={16} />} label="Lên đầu" busy={busyAction === 'top'} disabled={disabled || !hasSelection} onClick={onMoveToTop} />
        <ActionButton icon={<ArrowDown size={16} />} label="Xuống cuối" busy={busyAction === 'bottom'} disabled={disabled || !hasSelection} onClick={onMoveToBottom} />
      </div>

      {queue?.warnings?.length ? (
        <div className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          {queue.warnings.slice(0, 3).map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      ) : null}

      {actionMessage ? <div className="mt-4 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">{actionMessage}</div> : null}
    </section>
  );
}

function ActionButton({
  icon,
  label,
  busy,
  disabled,
  danger,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  busy: boolean;
  disabled?: boolean;
  danger?: boolean;
  onClick: () => void;
}) {
  const base = danger
    ? 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100'
    : 'border-line bg-surface text-ink hover:bg-blue-50 hover:text-brand';
  return (
    <button
      type="button"
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${base}`}
      disabled={disabled || busy}
      onClick={onClick}
    >
      {icon}
      {busy ? 'Đang xử lý...' : label}
    </button>
  );
}

function Metric({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className={`rounded-md p-3 ${danger && value > 0 ? 'bg-rose-50 text-rose-700' : 'bg-surface text-ink'}`}>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    running: 'Đang chạy',
    pausing: 'Đang yêu cầu tạm dừng',
    paused: 'Đã tạm dừng',
    resuming: 'Đang tiếp tục',
    completed: 'Hoàn thành',
    completed_with_warnings: 'Hoàn thành có cảnh báo',
    failed: 'Thất bại',
    cancel_requested: 'Đang yêu cầu hủy',
    cancelled: 'Đã hủy',
  };
  return labels[status] ?? status;
}
