import { Grid3X3, List, Search } from 'lucide-react';
import GlassButton from '../glass/GlassButton';

export type SourceMediaViewMode = 'grid' | 'list';
export type SourceMediaSortMode = 'name' | 'duration_desc' | 'duration_asc' | 'quality_desc';

export default function SourceMediaFilters({
  search,
  orientation,
  status,
  audio,
  viewMode,
  sortMode,
  onSearchChange,
  onOrientationChange,
  onStatusChange,
  onAudioChange,
  onViewModeChange,
  onSortModeChange,
}: {
  search: string;
  orientation: string;
  status: string;
  audio: string;
  viewMode: SourceMediaViewMode;
  sortMode: SourceMediaSortMode;
  onSearchChange: (value: string) => void;
  onOrientationChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onAudioChange: (value: string) => void;
  onViewModeChange: (value: SourceMediaViewMode) => void;
  onSortModeChange: (value: SourceMediaSortMode) => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-white/10 bg-white/5 p-3">
      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
        <input
          className="h-10 w-full rounded-md border border-white/15 bg-slate-950/80 pl-9 pr-3 text-sm text-white outline-none focus:border-cyan-300/70"
          placeholder="Tìm theo tên file..."
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      <div className="grid gap-2 sm:grid-cols-4">
        <Select label="Tỉ lệ" value={orientation} onChange={onOrientationChange} options={[['all', 'Tất cả'], ['vertical', 'Dọc'], ['horizontal', 'Ngang'], ['square', 'Vuông']]} />
        <Select label="Trạng thái" value={status} onChange={onStatusChange} options={[['all', 'Tất cả'], ['valid', 'Tốt'], ['warning', 'Cảnh báo'], ['unreadable', 'Lỗi']]} />
        <Select label="Audio" value={audio} onChange={onAudioChange} options={[['all', 'Tất cả'], ['with_audio', 'Có audio'], ['no_audio', 'Không audio']]} />
        <Select label="Sắp xếp" value={sortMode} onChange={(value) => onSortModeChange(value as SourceMediaSortMode)} options={[['name', 'Tên file'], ['quality_desc', 'Điểm tốt nhất'], ['duration_desc', 'Dài nhất'], ['duration_asc', 'Ngắn nhất']]} />
      </div>
      <div className="flex gap-2">
        <GlassButton className="px-3" variant={viewMode === 'grid' ? 'primary' : 'secondary'} onClick={() => onViewModeChange('grid')}>
          <Grid3X3 size={16} />
          Grid
        </GlassButton>
        <GlassButton className="px-3" variant={viewMode === 'list' ? 'primary' : 'secondary'} onClick={() => onViewModeChange('list')}>
          <List size={16} />
          List
        </GlassButton>
      </div>
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-slate-400">{label}</span>
      <select
        className="h-10 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none focus:border-cyan-300/70"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}
