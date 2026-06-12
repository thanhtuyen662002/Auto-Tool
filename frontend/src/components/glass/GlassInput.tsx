import type { InputHTMLAttributes } from 'react';

type Props = InputHTMLAttributes<HTMLInputElement> & { label?: string };

export default function GlassInput({ label, className = '', ...props }: Props) {
  return (
    <label className="block">
      {label ? <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span> : null}
      <input className={`h-11 w-full rounded-md border border-white/15 bg-slate-950/75 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15 ${className}`} {...props} />
    </label>
  );
}
