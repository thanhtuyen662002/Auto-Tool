import type { NormalizedResultItem, ResultViewMode } from '../../utils/resultStatus';
import ResultsEmptyState from './ResultsEmptyState';
import ResultVideoCard from './ResultVideoCard';

export default function ResultVideoGrid({
  items,
  selectedIds,
  selectionMode,
  selectionLabel = 'Chọn xuất',
  viewMode,
  canSelectItem = (item) => item.exportEligible,
  onToggleSelected,
  onPreview,
  onCopyPath,
  onRevealFile,
  onCopyCaption,
  onShowLog,
}: {
  items: NormalizedResultItem[];
  selectedIds: Set<string>;
  selectionMode: boolean;
  selectionLabel?: string;
  viewMode: ResultViewMode;
  canSelectItem?: (item: NormalizedResultItem) => boolean;
  onToggleSelected: (item: NormalizedResultItem) => void;
  onPreview: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
}) {
  if (!items.length) {
    return (
      <ResultsEmptyState
        title="Không có kết quả phù hợp"
        message="Đổi bộ lọc hoặc từ khóa tìm kiếm để xem các video ở trạng thái khác."
      />
    );
  }

  return (
    <div className={viewMode === 'compact' ? 'grid gap-3' : 'grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'}>
      {items.map((item) => (
        <ResultVideoCard
          item={item}
          key={item.id}
          selected={selectedIds.has(item.id)}
          selectionMode={selectionMode}
          selectionLabel={selectionLabel}
          viewMode={viewMode}
          canSelectItem={canSelectItem}
          onCopyCaption={onCopyCaption}
          onCopyPath={onCopyPath}
          onRevealFile={onRevealFile}
          onPreview={onPreview}
          onShowLog={onShowLog}
          onToggleSelected={onToggleSelected}
        />
      ))}
    </div>
  );
}
