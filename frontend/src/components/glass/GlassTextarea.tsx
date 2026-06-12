import type { TextareaHTMLAttributes } from 'react';

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string };

export default function GlassTextarea({ label, className = '', ...props }: Props) {
  return (
    <label className="block">
      {label ? <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span> : null}
      <textarea className={`min-h-24 w-full rounded-md border border-white/15 bg-slate-950/90 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15 ${className}`} {...props} />
    </label>
  );
}
