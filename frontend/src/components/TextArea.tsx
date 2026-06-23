interface TextAreaProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  className?: string;
  spellCheck?: boolean;
  autoComplete?: string;
}

export default function TextArea({
  label,
  value,
  onChange,
  rows = 4,
  placeholder,
  className = '',
  spellCheck = true,
  autoComplete,
}: TextAreaProps) {
  const minHeightClass = rows >= 6 ? 'min-h-40' : 'min-h-24';

  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      <textarea
        className={`w-full resize-y rounded-md border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100 ${minHeightClass} ${className}`}
        lang="vi"
        spellCheck={spellCheck}
        autoComplete={autoComplete}
        rows={rows}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
