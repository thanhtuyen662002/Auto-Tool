import { FileText, TriangleAlert } from 'lucide-react';
import GlassBadge from '../glass/GlassBadge';
import GlassCard from '../glass/GlassCard';
import GlassProgress from '../glass/GlassProgress';

export default function JobProgressPanel({ progress, currentStep, completed, total, failed, warnings, onViewLog }: { progress: number; currentStep: string; completed: number; total: number; failed: number; warnings?: number; onViewLog?: () => void }) {
  return (
    <GlassCard strong className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-xs font-semibold uppercase text-slate-400">Đang xử lý</div><div className="mt-1 font-semibold text-white">{currentStep || 'Chuẩn bị'}</div></div><GlassBadge variant={failed ? 'warning' : 'processing'}>{progress}%</GlassBadge></div>
      <div className="mt-4"><GlassProgress value={progress} /></div>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs"><Metric label="Đã xong" value={`${completed}/${total}`} /><Metric label="Cảnh báo" value={String(warnings ?? 0)} /><Metric label="Lỗi" value={String(failed)} danger={failed > 0} /></div>
      {onViewLog ? <button className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-cyan-200" type="button" onClick={onViewLog}><FileText size={14} /> Xem log kỹ thuật</button> : null}
      {failed > 0 ? <div className="mt-3 flex items-center gap-2 text-xs text-amber-200"><TriangleAlert size={14} /> Batch vẫn tiếp tục với các video còn lại.</div> : null}
    </GlassCard>
  );
}

function Metric({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return <div className="rounded-md bg-black/20 p-2"><div className="text-slate-400">{label}</div><div className={`mt-1 font-semibold ${danger ? 'text-rose-200' : 'text-white'}`}>{value}</div></div>;
}
