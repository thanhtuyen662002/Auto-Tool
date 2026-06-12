import { CheckCircle2, Info, ShieldCheck } from 'lucide-react';
import GlassBadge from '../glass/GlassBadge';
import GlassCard from '../glass/GlassCard';

export default function RightInsightPanel({ preset, workflow, reviewRequired, captionSource, warnings = [] }: { preset: string; workflow: string[]; reviewRequired: boolean; captionSource?: string; warnings?: string[] }) {
  return (
    <GlassCard strong className="sticky top-24 p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-white"><Info size={17} className="text-cyan-200" /> Workflow hiện tại</div>
      <div className="mt-4"><div className="text-xs uppercase text-slate-500">Preset</div><div className="mt-1 font-semibold text-white">{preset}</div></div>
      <div className="mt-4 grid gap-2">{workflow.map((step, index) => <div className="flex items-center gap-2 text-sm text-slate-300" key={step}><span className="grid h-5 w-5 place-items-center rounded-full border border-white/15 text-[10px] text-cyan-200">{index + 1}</span>{step}</div>)}</div>
      <div className="mt-5 grid gap-2 border-t border-white/10 pt-4 text-sm"><div className="flex items-center justify-between"><span className="text-slate-400">Review</span><GlassBadge variant={reviewRequired ? 'needs_review' : 'success'}>{reviewRequired ? 'Cần kiểm tra' : 'Tự động'}</GlassBadge></div>{captionSource ? <div className="flex items-start gap-2 rounded-md bg-black/20 p-3 text-xs text-slate-300"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-200" />{captionSource}</div> : null}</div>
      {warnings.length ? <div className="mt-4 grid gap-2">{warnings.map((warning) => <div key={warning} className="text-xs text-amber-200">{warning}</div>)}</div> : <div className="mt-4 flex items-center gap-2 text-xs text-emerald-200"><CheckCircle2 size={14} /> Sẵn sàng khi đã chọn folder.</div>}
    </GlassCard>
  );
}
