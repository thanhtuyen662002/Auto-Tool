import type { Preset } from '../types/project';

interface PresetSelectorProps {
  presets: Preset[];
  selectedName: string;
  onSelect: (preset: Preset) => void;
}

export default function PresetSelector({ presets, selectedName, onSelect }: PresetSelectorProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {presets.map((preset) => {
        const active = preset.name === selectedName;
        return (
          <button
            key={preset.name}
            type="button"
            className={`rounded-md border px-4 py-3 text-left text-sm font-semibold transition ${
              active
                ? 'border-brand bg-blue-50 text-brand'
                : 'border-line bg-white text-ink hover:border-brand'
            }`}
            onClick={() => onSelect(preset)}
          >
            {presetNameVi(preset.name)}
          </button>
        );
      })}
    </div>
  );
}

function presetNameVi(name: string): string {
  const labels: Record<string, string> = {
    'Light Recut': 'Cắt nhẹ',
    'Balanced Recut': 'Cắt cân bằng',
    'Aggressive Remix': 'Remix mạnh',
  };
  return labels[name] ?? name;
}
