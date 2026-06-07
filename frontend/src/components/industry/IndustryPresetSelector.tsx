import type { ApplyIndustryPresetOptions, IndustryPreset } from '../../types/project';
import { DEFAULT_INDUSTRY_APPLY_OPTIONS, videoStyleLabelForPreset } from '../../utils/industryPresetApply';

interface IndustryPresetSelectorProps {
  presets: IndustryPreset[];
  selectedPresetId?: string | null;
  applyOptions?: ApplyIndustryPresetOptions;
  compact?: boolean;
  onApplyOptionsChange?: (options: ApplyIndustryPresetOptions) => void;
  onSelect: (presetId: string) => void;
}

const OPTION_LABELS: Array<{ key: keyof ApplyIndustryPresetOptions; label: string }> = [
  { key: 'apply_timeline', label: 'Áp dụng style video' },
  { key: 'apply_visual_style', label: 'Áp dụng overlay/subtitle' },
  { key: 'apply_tts_voice', label: 'Áp dụng giọng đọc' },
  { key: 'apply_script_variation', label: 'Áp dụng script/caption tone' },
  { key: 'apply_edit_strength', label: 'Áp dụng mức độ chỉnh sửa' },
];

export default function IndustryPresetSelector({
  presets,
  selectedPresetId,
  applyOptions = DEFAULT_INDUSTRY_APPLY_OPTIONS,
  compact = false,
  onApplyOptionsChange,
  onSelect,
}: IndustryPresetSelectorProps) {
  const selected = presets.find((preset) => preset.id === selectedPresetId) ?? presets[0];

  if (!presets.length) {
    return (
      <div className="rounded-md border border-line bg-surface p-4 text-sm text-muted">
        Chưa tải được danh sách ngành hàng.
      </div>
    );
  }

  function updateOption(key: keyof ApplyIndustryPresetOptions, value: boolean) {
    onApplyOptionsChange?.({ ...applyOptions, [key]: value });
  }

  return (
    <div className="grid gap-4">
      <label className="block">
        <span className="mb-1 block text-sm font-medium text-ink">Ngành hàng sản phẩm</span>
        <select
          className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-blue-100"
          value={selected?.id ?? ''}
          onChange={(event) => onSelect(event.target.value)}
        >
          {presets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.name}
            </option>
          ))}
        </select>
      </label>

      {selected ? (
        <div className="rounded-md border border-line bg-surface p-4">
          <div className="text-sm font-semibold text-ink">{selected.name}</div>
          <p className="mt-1 text-sm leading-relaxed text-muted">{selected.description}</p>
          <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <SummaryItem label="Video style" value={videoStyleLabelForPreset(selected)} />
            <SummaryItem label="Timeline" value={selected.timeline_template_id} />
            <SummaryItem label="Overlay" value={selected.visual_style_preset_id} />
            <SummaryItem label="Voice" value={selected.default_tts_voice} />
            <SummaryItem label="Edit" value={selected.default_edit_strength} />
            <SummaryItem label="Script" value={selected.script_variation_mode} />
          </div>
          {!compact ? (
            <>
              <div className="mt-3 text-sm">
                <span className="font-medium text-ink">Caption tone: </span>
                <span className="text-muted">{selected.caption_tone}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {selected.hashtag_suggestions.map((tag) => (
                  <span key={tag} className="rounded bg-white px-2 py-1 text-xs font-medium text-muted">
                    {tag}
                  </span>
                ))}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      {onApplyOptionsChange ? (
        <div className="grid gap-2 rounded-md border border-line bg-white p-3 text-sm sm:grid-cols-2">
          {OPTION_LABELS.map((item) => (
            <label key={item.key} className="flex items-center gap-2">
              <input
                className="h-4 w-4 accent-brand"
                type="checkbox"
                checked={applyOptions[item.key]}
                onChange={(event) => updateOption(item.key, event.target.checked)}
              />
              <span>{item.label}</span>
            </label>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-white px-3 py-2">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className="mt-0.5 font-semibold text-ink">{value}</div>
    </div>
  );
}

