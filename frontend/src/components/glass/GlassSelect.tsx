import type { SelectHTMLAttributes } from 'react';

type Props = SelectHTMLAttributes<HTMLSelectElement> & { label?: string };

export default function GlassSelect({ label, className = '', children, ...props }: Props) {
  return (
    <label className="block">
      {label ? <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span> : null}
      <select className={`h-11 w-full rounded-md border border-white/15 bg-slate-950/75 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15 ${className}`} {...props}>
        {children}
      </select>
    </label>
  );
}
