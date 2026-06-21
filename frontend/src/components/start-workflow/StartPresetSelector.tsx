import { Wand2 } from 'lucide-react';
import type { StartPresetViewModel, StartWorkflowMode } from '../../types/startWorkflow';
import GlassCard from '../glass/GlassCard';
import StartPresetCard from './StartPresetCard';

export default function StartPresetSelector({
  mode,
  presets,
  selectedPresetId,
  recommendedPreset,
  recommendationReason,
  onSelect,
}: {
  mode: StartWorkflowMode;
  presets: StartPresetViewModel[];
  selectedPresetId: string;
  recommendedPreset?: StartPresetViewModel;
  recommendationReason?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-white">Chọn kiểu xử lý</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            {mode === 'silent_immersive' ? 'Không thoại / immersive' : 'Có thoại / cần dịch'}
          </p>
        </div>
        {recommendedPreset ? (
          <button
            className="inline-flex items-center gap-2 rounded-md border border-emerald-300/25 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/15"
            type="button"
            onClick={() => onSelect(recommendedPreset.id)}
          >
            <Wand2 size={14} />
            Dùng gợi ý: {recommendedPreset.name}
          </button>
        ) : null}
      </div>
      {recommendedPreset ? (
        <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm leading-6 text-emerald-100">
          <span className="font-semibold">Gợi ý cho bạn: {recommendedPreset.name}.</span> {recommendationReason || 'Kiểu xử lý này phù hợp nhất với lô video hiện tại.'}
        </div>
      ) : null}
      <div className="grid gap-3 md:grid-cols-2">
        {presets.map((preset) => (
          <StartPresetCard active={selectedPresetId === preset.id} key={preset.id} preset={preset} onSelect={onSelect} />
        ))}
      </div>
    </GlassCard>
  );
}
