export default function GlassProgress({ value, label }: { value: number; label?: string }) {
  const normalized = Math.max(0, Math.min(100, value));
  return (
    <div>
      {label ? <div className="mb-2 flex justify-between text-xs text-slate-300"><span>{label}</span><span>{normalized}%</span></div> : null}
      <div className="h-2 overflow-hidden rounded-full bg-white/8"><div className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-violet-400 transition-all" style={{ width: `${normalized}%` }} /></div>
    </div>
  );
}
