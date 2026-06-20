interface SliderInputProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

export default function SliderInput({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
}: SliderInputProps) {
  return (
    <label className="block rounded-md border border-white/10 bg-slate-950/45 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <span className="mb-2 flex items-center justify-between gap-3 text-sm font-medium text-slate-100">
        <span>{label}</span>
        <span className="min-w-12 rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-right text-xs text-slate-300">
          {value}
        </span>
      </span>
      <input
        className="w-full accent-cyan-300"
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
