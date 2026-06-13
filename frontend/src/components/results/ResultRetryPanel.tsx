import { RotateCcw, ShieldAlert } from 'lucide-react';
import type { NormalizedResultItem } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';

export default function ResultRetryPanel({
  failedItems,
  busy,
  onRetryFailed,
}: {
  failedItems: NormalizedResultItem[];
  busy: boolean;
  onRetryFailed: () => void;
}) {
  if (!failedItems.length) return null;
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 shrink-0 text-rose-300" size={20} />
        <div className="min-w-0">
          <h2 className="font-semibold text-white">Retry lỗi</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Có {failedItems.length} output lỗi hoặc không qua QA. Retry sẽ tạo job mới bằng endpoint Douyin retry hiện có.
          </p>
        </div>
      </div>
      <div className="grid gap-2">
        {failedItems.slice(0, 4).map((item) => (
          <div className="min-w-0 rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-xs" key={item.id}>
            <div className="truncate font-semibold text-rose-100">{item.filename}</div>
            <div className="mt-1 text-rose-200/80">{item.failedStep || item.errorText || 'Render/QA thất bại'}</div>
          </div>
        ))}
      </div>
      <GlassButton variant="danger" loading={busy} onClick={onRetryFailed}>
        <RotateCcw size={16} />
        Thử lại các video lỗi
      </GlassButton>
    </GlassCard>
  );
}
