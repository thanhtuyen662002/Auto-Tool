import { ChevronDown, SlidersHorizontal } from 'lucide-react';
import type { ReactNode } from 'react';

export default function AdvancedSettingsDrawer({ open, onToggle, children, onReset }: { open: boolean; onToggle: () => void; children: ReactNode; onReset?: () => void }) {
  return (
    <section className="glass-card overflow-hidden">
      <div className="flex items-center justify-between gap-3 p-4">
        <button className="flex flex-1 items-center gap-2 text-left text-sm font-semibold text-white" type="button" onClick={onToggle} aria-expanded={open}>
          <SlidersHorizontal size={17} className="text-cyan-200" /> Cài đặt nâng cao
          <ChevronDown size={16} className={`ml-auto transition ${open ? 'rotate-180' : ''}`} />
        </button>
        {open && onReset ? <button className="text-xs font-semibold text-slate-300 hover:text-cyan-200" type="button" onClick={onReset}>Đặt lại preset</button> : null}
      </div>
      {open ? <div className="border-t border-white/10 p-4">{children}</div> : null}
    </section>
  );
}
