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
    <label className="block rounded-md border border-line bg-white p-3">
      <span className="mb-2 flex items-center justify-between gap-3 text-sm font-medium text-ink">
        <span>{label}</span>
        <span className="min-w-12 rounded bg-surface px-2 py-1 text-right text-xs text-muted">
          {value}
        </span>
      </span>
      <input
        className="w-full accent-brand"
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
