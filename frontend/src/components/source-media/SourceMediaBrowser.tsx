import { useEffect, useMemo, useState } from 'react';
import type {
  SourceBrowserMediaItem,
  SourceBrowserPriority,
  SourceFolderScanResult,
  SourceMediaSelectionResult,
} from '../../types/project';
import { createSourceMediaSelection, scanSourceMedia } from '../../services/sourceMediaApi';
import ApiErrorBox from '../ApiErrorBox';
import GlassCard from '../glass/GlassCard';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SourceMediaBulkActions from './SourceMediaBulkActions';
import SourceMediaEmptyState from './SourceMediaEmptyState';
import SourceMediaFilters from './SourceMediaFilters';
import type { SourceMediaSortMode, SourceMediaViewMode } from './SourceMediaFilters';
import SourceMediaGrid from './SourceMediaGrid';
import SourceMediaList from './SourceMediaList';
import SourceMediaPreviewModal from './SourceMediaPreviewModal';
import SourceMediaSelectionSummary from './SourceMediaSelectionSummary';
import SourceMediaSkeleton from './SourceMediaSkeleton';
import SourceMediaToolbar from './SourceMediaToolbar';

export type SourceMediaBrowserApplyPayload = {
  selectionId: string | null;
  selectedPaths: string[];
  scan: SourceFolderScanResult;
  selection: SourceMediaSelectionResult;
};

export default function SourceMediaBrowser({
  folderPath,
  selectedPaths,
  sourceSelectionId,
  onApply,
}: {
  folderPath: string;
  selectedPaths: string[];
  sourceSelectionId?: string | null;
  onApply: (payload: SourceMediaBrowserApplyPayload) => void;
}) {
  const [scanResult, setScanResult] = useState<SourceFolderScanResult | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [priorities, setPriorities] = useState<Record<string, SourceBrowserPriority>>({});
  const [search, setSearch] = useState('');
  const [orientation, setOrientation] = useState('all');
  const [status, setStatus] = useState('all');
  const [audio, setAudio] = useState('all');
  const [sortMode, setSortMode] = useState<SourceMediaSortMode>('quality_desc');
  const [viewMode, setViewMode] = useState<SourceMediaViewMode>('grid');
  const [recursive, setRecursive] = useState(false);
  const [generateThumbnails, setGenerateThumbnails] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selectionBusy, setSelectionBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [previewItem, setPreviewItem] = useState<SourceBrowserMediaItem | null>(null);
  const [activeSelectionId, setActiveSelectionId] = useState<string | null>(sourceSelectionId || null);

  useEffect(() => {
    setActiveSelectionId(sourceSelectionId || null);
  }, [sourceSelectionId]);

  useEffect(() => {
    if (!scanResult) return;
    const selectedPathSet = new Set(selectedPaths);
    const nextSelected = new Set<string>();
    const nextPriorities: Record<string, SourceBrowserPriority> = {};
    for (const item of scanResult.items) {
      const shouldSelect = selectedPathSet.size ? selectedPathSet.has(item.path) : item.selected && item.status !== 'unreadable';
      if (shouldSelect) nextSelected.add(item.id);
      nextPriorities[item.id] = item.priority || 'normal';
    }
    setSelectedIds(nextSelected);
    setPriorities(nextPriorities);
  }, [scanResult, selectedPaths]);

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    const items = (scanResult?.items || []).filter((item) => {
      if (keyword && !item.filename.toLowerCase().includes(keyword) && !item.path.toLowerCase().includes(keyword)) return false;
      if (orientation !== 'all' && item.orientation !== orientation) return false;
      if (status !== 'all' && item.status !== status) return false;
      if (audio === 'with_audio' && !item.has_audio) return false;
      if (audio === 'no_audio' && item.has_audio) return false;
      return true;
    });
    return [...items].sort((a, b) => sortItems(a, b, sortMode));
  }, [audio, orientation, scanResult, search, sortMode, status]);

  const selectedItems = useMemo(() => {
    const items = scanResult?.items || [];
    return items.filter((item) => selectedIds.has(item.id));
  }, [scanResult, selectedIds]);

  async function runScan() {
    if (!folderPath.trim()) {
      setError('Bạn cần chọn folder video trước.');
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await scanSourceMedia({
        folder_path: folderPath,
        recursive,
        generate_thumbnails: generateThumbnails,
      });
      setScanResult(result);
      setMessage(`Đã scan ${result.total_files_found} file, chọn sẵn ${result.selected_count} video có thể dùng.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể scan source media.');
    } finally {
      setBusy(false);
    }
  }

  function toggleItem(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectVisible() {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const item of filteredItems) {
        if (item.status !== 'unreadable' && item.status !== 'missing') next.add(item.id);
      }
      return next;
    });
  }

  function setPriorityForSelected(priority: SourceBrowserPriority) {
    setPriorities((current) => {
      const next = { ...current };
      for (const id of selectedIds) next[id] = priority;
      return next;
    });
  }

  async function applySelection() {
    if (!scanResult) return;
    if (!selectedIds.size) {
      setError('Bạn chưa chọn video nào.');
      return;
    }
    setSelectionBusy(true);
    setError(null);
    try {
      const selectedItemIds = Array.from(selectedIds);
      const selectedSet = new Set(selectedItemIds);
      const result = await createSourceMediaSelection({
        folder_id: scanResult.folder_id,
        selected_item_ids: selectedItemIds,
        excluded_item_ids: scanResult.items.filter((item) => !selectedSet.has(item.id)).map((item) => item.id),
        priorities,
        selection_name: `selection-${new Date().toISOString().slice(0, 19)}`,
      });
      setActiveSelectionId(result.selection_id || null);
      setMessage(`Đã tạo selection với ${result.selected_count} video.`);
      onApply({
        selectionId: result.selection_id || null,
        selectedPaths: result.selected_paths,
        scan: scanResult,
        selection: result,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo selection.');
    } finally {
      setSelectionBusy(false);
    }
  }

  return (
    <GlassCard className="grid gap-4 p-4" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">Source Media Browser</h2>
          <p className="mt-1 text-sm text-slate-400">Scan, lọc và chọn đúng video sẽ đưa vào batch render.</p>
        </div>
        {message ? <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-sm text-emerald-100">{message}</div> : null}
      </div>
      <ApiErrorBox error={error} />
      <NotifyOnChange value={message} variant="success" />
      <SourceMediaToolbar
        folderPath={folderPath}
        recursive={recursive}
        generateThumbnails={generateThumbnails}
        busy={busy}
        hasResult={Boolean(scanResult)}
        onRecursiveChange={setRecursive}
        onGenerateThumbnailsChange={setGenerateThumbnails}
        onScan={runScan}
        onRescan={runScan}
      />
      {busy ? <SourceMediaSkeleton /> : null}
      {!busy && !scanResult ? <SourceMediaEmptyState message="Chưa có dữ liệu scan. Bấm Scan media để xem video nguồn." /> : null}
      {!busy && scanResult ? (
        <>
          <SourceMediaSelectionSummary totalCount={scanResult.items.length} selectedItems={selectedItems} selectionId={activeSelectionId} />
          <SourceMediaFilters
            search={search}
            orientation={orientation}
            status={status}
            audio={audio}
            sortMode={sortMode}
            viewMode={viewMode}
            onSearchChange={setSearch}
            onOrientationChange={setOrientation}
            onStatusChange={setStatus}
            onAudioChange={setAudio}
            onSortModeChange={setSortMode}
            onViewModeChange={setViewMode}
          />
          <SourceMediaBulkActions
            selectedCount={selectedIds.size}
            totalCount={filteredItems.length}
            busy={selectionBusy}
            onSelectVisible={selectVisible}
            onClearSelection={() => setSelectedIds(new Set())}
            onPriorityChange={setPriorityForSelected}
            onApplySelection={applySelection}
          />
          {filteredItems.length ? (
            viewMode === 'grid' ? (
              <SourceMediaGrid
                items={filteredItems}
                folderId={scanResult.folder_id}
                selectedIds={selectedIds}
                priorities={priorities}
                onToggle={toggleItem}
                onPreview={setPreviewItem}
                onPriorityChange={(id, priority) => setPriorities((current) => ({ ...current, [id]: priority }))}
              />
            ) : (
              <SourceMediaList
                items={filteredItems}
                selectedIds={selectedIds}
                priorities={priorities}
                onToggle={toggleItem}
                onPreview={setPreviewItem}
                onPriorityChange={(id, priority) => setPriorities((current) => ({ ...current, [id]: priority }))}
              />
            )
          ) : (
            <SourceMediaEmptyState message="Không có video phù hợp với bộ lọc hiện tại." />
          )}
        </>
      ) : null}
      <SourceMediaPreviewModal item={previewItem} onClose={() => setPreviewItem(null)} />
    </GlassCard>
  );
}

function sortItems(a: SourceBrowserMediaItem, b: SourceBrowserMediaItem, mode: SourceMediaSortMode): number {
  if (mode === 'duration_desc') return (b.duration_seconds || 0) - (a.duration_seconds || 0);
  if (mode === 'duration_asc') return (a.duration_seconds || 0) - (b.duration_seconds || 0);
  if (mode === 'quality_desc') return (b.quality_score || 0) - (a.quality_score || 0);
  return a.filename.localeCompare(b.filename, 'vi');
}
