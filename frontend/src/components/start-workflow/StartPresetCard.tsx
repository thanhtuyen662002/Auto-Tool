import { CheckCircle2, Sparkles, Zap } from 'lucide-react';
import type { StartPresetViewModel } from '../../types/startWorkflow';
import GlassBadge from '../glass/GlassBadge';

export default function StartPresetCard({
  preset,
  active,
  onSelect,
}: {
  preset: StartPresetViewModel;
  active: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <button
      className={`group min-h-[150px] rounded-md border p-4 text-left transition focus:outline-none focus:ring-2 focus:ring-cyan-300/40 ${
        active ? 'border-cyan-300/70 bg-cyan-300/12 shadow-[0_0_30px_rgba(34,211,238,0.14)]' : 'border-white/10 bg-white/5 hover:border-cyan-300/35 hover:bg-white/8'
      }`}
      type="button"
      onClick={() => onSelect(preset.id)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`grid h-9 w-9 place-items-center rounded-md ${active ? 'bg-cyan-300 text-slate-950' : 'bg-white/8 text-cyan-200'}`}>
            {preset.autoRender ? <Zap size={18} /> : <Sparkles size={18} />}
          </span>
          <div>
            <div className="font-semibold text-white">{preset.name}</div>
            <div className="mt-0.5 text-xs text-slate-500">{preset.autoRender ? 'Xuất ngay' : preset.reviewRequired ? 'Cần duyệt' : 'Không cần duyệt'}</div>
          </div>
        </div>
        {active ? <CheckCircle2 className="shrink-0 text-cyan-200" size={18} /> : null}
      </div>
      <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-300">{preset.description}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {preset.recommended ? <GlassBadge variant="success">Khuyên dùng</GlassBadge> : null}
        {preset.badge ? <GlassBadge variant={preset.autoRender ? 'warning' : 'ready'}>{preset.badge}</GlassBadge> : null}
      </div>
    </button>
  );
}
