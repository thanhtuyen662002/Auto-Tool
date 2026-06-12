import { CheckSquare, Grid3X3, List, Search, Square, X } from 'lucide-react';
import type { ResultFilter, ResultSort, ResultSummary, ResultViewMode } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';

const filters: Array<{ value: ResultFilter; label: string; countKey?: keyof ResultSummary }> = [
  { value: 'all', label: 'Tất cả', countKey: 'total' },
  { value: 'ready', label: 'Sẵn sàng', countKey: 'ready' },
  { value: 'warnings', label: 'Cảnh báo', countKey: 'warnings' },
  { value: 'failed', label: 'Lỗi', countKey: 'failed' },
  { value: 'qa_failed', label: 'QA lỗi', countKey: 'qaFailed' },
  { value: 'needs_review', label: 'Cần review', countKey: 'needsReview' },
];

export default function ResultsFilterBar({
  filter,
  onFilterChange,
  search,
  onSearchChange,
  sort,
  onSortChange,
  viewMode,
  onViewModeChange,
  selectionMode,
  onSelectionModeChange,
  selectedCount,
  totalSelectable,
  summary,
  onSelectAll,
  onClearSelection,
}: {
  filter: ResultFilter;
  onFilterChange: (value: ResultFilter) => void;
  search: string;
  onSearchChange: (value: string) => void;
  sort: ResultSort;
  onSortChange: (value: ResultSort) => void;
  viewMode: ResultViewMode;
  onViewModeChange: (value: ResultViewMode) => void;
  selectionMode: boolean;
  onSelectionModeChange: (value: boolean) => void;
  selectedCount: number;
  totalSelectable: number;
  summary: ResultSummary;
  onSelectAll: () => void;
  onClearSelection: () => void;
}) {
  return (
    <div className="glass-card-strong grid gap-4 p-4">
      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Lọc kết quả">
        {filters.map((item) => {
          const count = item.countKey ? summary[item.countKey] : 0;
          const active = filter === item.value;
          return (
            <button
              className={`min-h-9 rounded-md border px-3 py-2 text-sm font-semibold transition ${
                active
                  ? 'border-cyan-300/45 bg-cyan-300/12 text-cyan-100'
                  : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'
              }`}
              key={item.value}
              type="button"
              onClick={() => onFilterChange(item.value)}
            >
              {item.label} <span className="ml-1 text-xs text-slate-400">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_180px_auto]">
        <label className="relative block min-w-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input
            className="h-11 w-full rounded-md border border-white/15 bg-slate-950/70 pl-9 pr-9 text-sm text-white placeholder:text-slate-500"
            placeholder="Tìm theo tên file, caption, cảnh báo..."
            type="search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          {search ? (
            <button
              className="absolute right-2 top-1/2 rounded-md p-1 text-slate-400 hover:bg-white/10 hover:text-white"
              type="button"
              aria-label="Xóa tìm kiếm"
              onClick={() => onSearchChange('')}
            >
              <X size={16} />
            </button>
          ) : null}
        </label>

        <select
          className="h-11 rounded-md border border-white/15 bg-slate-950/70 px-3 text-sm"
          value={sort}
          onChange={(event) => onSortChange(event.target.value as ResultSort)}
          aria-label="Sắp xếp kết quả"
        >
          <option value="index_asc">Index tăng dần</option>
          <option value="index_desc">Index giảm dần</option>
          <option value="status">Ưu tiên lỗi</option>
          <option value="duration_desc">Duration dài nhất</option>
        </select>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-md border border-white/10 bg-white/5 p-1" aria-label="Chế độ xem">
            <button
              className={`rounded px-2.5 py-2 ${viewMode === 'grid' ? 'bg-cyan-300 text-slate-950' : 'text-slate-300 hover:bg-white/10'}`}
              type="button"
              title="Grid view"
              onClick={() => onViewModeChange('grid')}
            >
              <Grid3X3 size={16} />
            </button>
            <button
              className={`rounded px-2.5 py-2 ${viewMode === 'compact' ? 'bg-cyan-300 text-slate-950' : 'text-slate-300 hover:bg-white/10'}`}
              type="button"
              title="Compact view"
              onClick={() => onViewModeChange('compact')}
            >
              <List size={16} />
            </button>
          </div>
          <GlassButton className="px-3" variant={selectionMode ? 'primary' : 'secondary'} onClick={() => onSelectionModeChange(!selectionMode)}>
            {selectionMode ? <CheckSquare size={16} /> : <Square size={16} />}
            Chọn
          </GlassButton>
          {selectionMode ? (
            <>
              <GlassButton className="px-3" variant="ghost" disabled={!totalSelectable} onClick={onSelectAll}>
                Chọn tất cả
              </GlassButton>
              <GlassButton className="px-3" variant="ghost" disabled={!selectedCount} onClick={onClearSelection}>
                Bỏ chọn
              </GlassButton>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
