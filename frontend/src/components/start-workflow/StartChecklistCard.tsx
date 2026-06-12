import { AlertTriangle, CheckCircle2, CircleDotDashed, XCircle } from 'lucide-react';
import type { StartChecklistItem } from '../../types/startWorkflow';
import GlassCard from '../glass/GlassCard';

export default function StartChecklistCard({ items }: { items: StartChecklistItem[] }) {
  return (
    <GlassCard className="grid gap-3 p-5" strong>
      <h2 className="font-semibold text-white">Checklist trước khi start</h2>
      <div className="grid gap-2">
        {items.map((item) => {
          const Icon = item.status === 'ok' ? CheckCircle2 : item.status === 'warning' ? AlertTriangle : XCircle;
          const tone = item.status === 'ok' ? 'text-emerald-300' : item.status === 'warning' ? 'text-amber-300' : 'text-rose-300';
          return (
            <div className="flex items-start gap-3 rounded-md border border-white/10 bg-white/5 p-3 text-sm" key={item.id}>
              <Icon className={`mt-0.5 shrink-0 ${tone}`} size={17} />
              <div className="min-w-0">
                <div className="font-semibold text-slate-100">{item.label}: {statusLabel(item.status)}</div>
                {item.message ? <div className="mt-1 text-xs leading-5 text-slate-400">{item.message}</div> : null}
              </div>
            </div>
          );
        })}
      </div>
      {!items.length ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <CircleDotDashed size={16} />
          Đang chuẩn bị checklist.
        </div>
      ) : null}
    </GlassCard>
  );
}

function statusLabel(status: StartChecklistItem['status']) {
  if (status === 'ok') return 'OK';
  if (status === 'warning') return 'Warning';
  return 'Missing';
}
