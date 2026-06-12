import { Check, Circle, TriangleAlert, X } from 'lucide-react';

export type WorkflowStepStatus = 'pending' | 'active' | 'done' | 'warning' | 'failed';

const iconByStatus = {
  pending: Circle,
  active: Circle,
  done: Check,
  warning: TriangleAlert,
  failed: X,
};

export default function WorkflowStepper({ steps }: { steps: Array<{ label: string; status: WorkflowStepStatus }> }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6" aria-label="Tiến trình workflow">
      {steps.map((step, index) => {
        const Icon = iconByStatus[step.status];
        const active = step.status === 'active';
        const danger = step.status === 'failed';
        const warning = step.status === 'warning';
        const done = step.status === 'done';
        return (
          <div className={`relative flex min-h-11 items-center gap-2 rounded-md border px-3 py-2 text-xs font-semibold ${active ? 'border-cyan-300/60 bg-cyan-300/12 text-cyan-100' : danger ? 'border-rose-300/35 bg-rose-300/10 text-rose-200' : warning ? 'border-amber-300/35 bg-amber-300/10 text-amber-200' : done ? 'border-emerald-300/30 bg-emerald-300/8 text-emerald-200' : 'border-white/10 bg-white/5 text-slate-400'}`} key={step.label}>
            <Icon size={15} className={active ? 'animate-pulse' : ''} />
            <span>{step.label}</span>
            <span className="ml-auto text-[10px] text-current/60">{index + 1}</span>
          </div>
        );
      })}
    </div>
  );
}
