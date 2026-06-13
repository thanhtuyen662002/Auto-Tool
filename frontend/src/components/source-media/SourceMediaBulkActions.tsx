import { CheckSquare, Square, Star } from 'lucide-react';
import type { SourceBrowserPriority } from '../../types/project';
import GlassButton from '../glass/GlassButton';

export default function SourceMediaBulkActions({
  selectedCount,
  totalCount,
  busy,
  onSelectVisible,
  onClearSelection,
  onPriorityChange,
  onApplySelection,
}: {
  selectedCount: number;
  totalCount: number;
  busy: boolean;
  onSelectVisible: () => void;
  onClearSelection: () => void;
  onPriorityChange: (priority: SourceBrowserPriority) => void;
  onApplySelection: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-white/10 bg-white/5 p-3">
      <div className="mr-auto text-sm text-slate-300">
        Đã chọn <span className="font-semibold text-white">{selectedCount}</span> / {totalCount}
      </div>
      <GlassButton className="px-3" variant="secondary" onClick={onSelectVisible}>
        <CheckSquare size={16} />
        Chọn tất cả
      </GlassButton>
      <GlassButton className="px-3" variant="ghost" onClick={onClearSelection}>
        <Square size={16} />
        Bỏ chọn
      </GlassButton>
      <label className="flex items-center gap-2 text-sm text-slate-300">
        <Star size={16} />
        Priority
        <select
          className="h-10 rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white"
          defaultValue="normal"
          onChange={(event) => onPriorityChange(event.target.value as SourceBrowserPriority)}
        >
          <option value="high">Cao</option>
          <option value="normal">Thường</option>
          <option value="low">Thấp</option>
        </select>
      </label>
      <GlassButton variant="primary" loading={busy} disabled={!selectedCount} onClick={onApplySelection}>
        Dùng video đã chọn
      </GlassButton>
    </div>
  );
}
