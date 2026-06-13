import type { SourceBrowserMediaItem, SourceBrowserPriority } from '../../types/project';
import SourceMediaCard from './SourceMediaCard';

export default function SourceMediaGrid({
  items,
  folderId,
  selectedIds,
  priorities,
  onToggle,
  onPreview,
  onPriorityChange,
}: {
  items: SourceBrowserMediaItem[];
  folderId: string;
  selectedIds: Set<string>;
  priorities: Record<string, SourceBrowserPriority>;
  onToggle: (id: string) => void;
  onPreview: (item: SourceBrowserMediaItem) => void;
  onPriorityChange: (id: string, priority: SourceBrowserPriority) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <SourceMediaCard
          key={item.id}
          item={item}
          folderId={folderId}
          selected={selectedIds.has(item.id)}
          priority={priorities[item.id] || item.priority || 'normal'}
          onToggle={() => onToggle(item.id)}
          onPreview={() => onPreview(item)}
          onPriorityChange={(priority) => onPriorityChange(item.id, priority)}
        />
      ))}
    </div>
  );
}
