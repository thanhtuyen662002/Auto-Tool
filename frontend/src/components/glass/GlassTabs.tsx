export default function GlassTabs<T extends string>({ items, value, onChange }: { items: Array<{ value: T; label: string }>; value: T; onChange: (value: T) => void }) {
  return (
    <div className="inline-flex rounded-md border border-white/15 bg-black/20 p-1">
      {items.map((item) => (
        <button key={item.value} className={`rounded px-3 py-1.5 text-sm font-semibold transition ${value === item.value ? 'bg-cyan-300 text-slate-950' : 'text-slate-300 hover:text-white'}`} type="button" onClick={() => onChange(item.value)}>{item.label}</button>
      ))}
    </div>
  );
}
