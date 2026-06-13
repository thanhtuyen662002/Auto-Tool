import type { SourceBrowserMediaItem } from '../../types/project';

export default function SourceMediaSelectionSummary({
  totalCount,
  selectedItems,
  selectionId,
}: {
  totalCount: number;
  selectedItems: SourceBrowserMediaItem[];
  selectionId?: string | null;
}) {
  const totalDuration = selectedItems.reduce((sum, item) => sum + (item.duration_seconds || 0), 0);
  const audioCount = selectedItems.filter((item) => item.has_audio).length;
  return (
    <div className="grid gap-2 rounded-md border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-50 sm:grid-cols-4">
      <Metric label="Tổng file" value={String(totalCount)} />
      <Metric label="Đã chọn" value={String(selectedItems.length)} />
      <Metric label="Có audio" value={String(audioCount)} />
      <Metric label="Thời lượng" value={`${Math.round(totalDuration)}s`} />
      {selectionId ? <div className="sm:col-span-4 text-xs text-cyan-100/80">Selection: {selectionId}</div> : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 p-2">
      <div className="font-semibold text-white">{value}</div>
      <div className="mt-1 text-xs text-cyan-100/80">{label}</div>
    </div>
  );
}
