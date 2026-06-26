import { Captions, CheckSquare, ChevronLeft, ChevronRight, Clipboard, FolderOpen, Square, Keyboard, FileSearch } from 'lucide-react';
import { useCallback, useEffect, useMemo } from 'react';
import { videoFileUrl } from '../../api/client';
import { captionBundle, type NormalizedResultItem } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassModal from '../glass/GlassModal';
import ResultStatusBadges from './ResultStatusBadges';

export default function ResultVideoPreviewModal({
  item,
  items = [],
  selected,
  selectionMode,
  selectionLabel = 'Chọn xuất',
  canSelectItem = (result) => result.exportEligible,
  onClose,
  onToggleSelected,
  onCopyPath,
  onRevealFile,
  onCopyCaption,
  onShowLog,
  onNavigate,
}: {
  item: NormalizedResultItem | null;
  items?: NormalizedResultItem[];
  selected: boolean;
  selectionMode: boolean;
  selectionLabel?: string;
  canSelectItem?: (item: NormalizedResultItem) => boolean;
  onClose: () => void;
  onToggleSelected: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
  onNavigate?: (item: NormalizedResultItem) => void;
}) {
  const hasCaption = Boolean(item && captionBundle(item));

  // Find the index of the current item in the list
  const currentIndex = useMemo(() => {
    if (!item || !items.length) return -1;
    return items.findIndex((x) => x.id === item.id);
  }, [item, items]);

  const hasPrev = currentIndex > 0;
  const hasNext = items.length > 0 && currentIndex < items.length - 1;

  const handlePrev = useCallback(() => {
    if (hasPrev && onNavigate) {
      onNavigate(items[currentIndex - 1]);
    }
  }, [hasPrev, currentIndex, items, onNavigate]);

  const handleNext = useCallback(() => {
    if (hasNext && onNavigate) {
      onNavigate(items[currentIndex + 1]);
    }
  }, [hasNext, currentIndex, items, onNavigate]);

  // Handle keyboard shortcuts
  useEffect(() => {
    if (!item) return undefined;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore key events if the user is typing in form fields
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.getAttribute('contenteditable') === 'true')) {
        return;
      }

      if (e.key === 'ArrowRight' || e.key.toLowerCase() === 'd') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft' || e.key.toLowerCase() === 'a') {
        e.preventDefault();
        handlePrev();
      } else if (e.key === ' ' || e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (canSelectItem(item)) {
          onToggleSelected(item);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [item, handleNext, handlePrev, onToggleSelected, canSelectItem]);

  const modalTitle = useMemo(() => {
    if (!item) return 'Xem trước';
    if (currentIndex !== -1 && items.length > 0) {
      return `[${currentIndex + 1} / ${items.length}] ${item.filename}`;
    }
    return item.filename;
  }, [item, currentIndex, items]);

  return (
    <GlassModal open={Boolean(item)} title={modalTitle} onClose={onClose}>
      {item ? (
        <div className="grid gap-5">
          {/* Video Player and Side Controls */}
          <div className="relative overflow-hidden rounded-lg border border-white/10 bg-black shadow-2xl">
            {item.path ? (
              <video
                key={item.path} // Re-mount video when path changes
                className="max-h-[60vh] w-full bg-black object-contain"
                controls
                autoPlay
                preload="metadata"
                src={videoFileUrl(item.path)}
              />
            ) : (
              <div className="grid aspect-video place-items-center text-slate-500 bg-slate-950/30">
                Không có video preview
              </div>
            )}

            {/* Floating Top-Right Selection Button */}
            {selectionMode && (
              <button
                onClick={() => onToggleSelected(item)}
                disabled={!canSelectItem(item)}
                className={`absolute right-4 top-4 z-30 flex items-center gap-1.5 rounded border px-3 py-1.5 text-xs font-semibold shadow-lg transition-all duration-200 focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed ${
                  selected 
                    ? 'bg-cyan-400 text-slate-950 border-cyan-300 hover:bg-cyan-300' 
                    : 'bg-black/75 text-slate-300 border-white/10 hover:bg-white/10 hover:text-white'
                }`}
                type="button"
              >
                {selected ? <CheckSquare size={14} className="shrink-0" /> : <Square size={14} className="shrink-0" />}
                {selected ? `Đã chọn` : selectionLabel}
              </button>
            )}

            {/* Floating Left/Right Navigation Chevrons */}
            {hasPrev && (
              <button
                onClick={handlePrev}
                className="absolute left-4 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full bg-black/70 text-slate-300 border border-white/10 hover:bg-cyan-400 hover:text-slate-950 hover:border-cyan-400 transition-all duration-200 shadow-xl z-20 focus:outline-none"
                title="Video trước (Mũi tên Trái / A)"
                type="button"
              >
                <ChevronLeft size={24} />
              </button>
            )}
            {hasNext && (
              <button
                onClick={handleNext}
                className="absolute right-4 top-1/2 -translate-y-1/2 flex h-11 w-11 items-center justify-center rounded-full bg-black/70 text-slate-300 border border-white/10 hover:bg-cyan-400 hover:text-slate-950 hover:border-cyan-400 transition-all duration-200 shadow-xl z-20 focus:outline-none"
                title="Video tiếp theo (Mũi tên Phải / D)"
                type="button"
              >
                <ChevronRight size={24} />
              </button>
            )}
          </div>

          {/* Video Metadata & Description */}
          <div className="grid gap-3 border-t border-white/5 pt-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ResultStatusBadges item={item} />
                <span className="text-xs text-slate-500">
                  Chỉ số: {String(item.index).padStart(3, '0')} {item.presetName ? `· Cấu hình: ${item.presetName}` : ''}
                </span>
              </div>
              {item.qaScorePercent != null ? (
                <span className="rounded-full bg-cyan-950/50 border border-cyan-400/20 px-2.5 py-0.5 text-xs font-medium text-cyan-300 shadow-sm">
                  Điểm QA: {item.qaScorePercent}%
                </span>
              ) : (
                <span className="text-xs text-slate-500 italic">Chưa kiểm tra QA</span>
              )}
            </div>

            {/* Path details */}
            <div className="grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
              <PathLine label="Video" value={item.path} />
              <PathLine label="Phụ đề Việt" value={item.subtitleFile} />
              <PathLine label="Giọng đọc (TTS)" value={item.voiceFile} />
              <PathLine label="Tệp log chi tiết" value={item.logFile} />
            </div>

            {/* Caption display */}
            {item.caption && (
              <div className="rounded-md border border-white/5 bg-white/2 p-3 text-sm leading-6 text-slate-200 font-normal italic select-text">
                "{item.caption}"
              </div>
            )}
          </div>

          {/* Action Footer & Keyboard Shortcuts Tip */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-t border-white/5 pt-4">
            {/* Action Buttons Row on a Single Line */}
            <div className="flex items-center gap-1.5 flex-nowrap overflow-x-auto whitespace-nowrap scrollbar-none py-1 min-w-0">
              <button
                disabled={!item.path}
                onClick={() => onCopyPath(item)}
                className="h-8 px-3 flex items-center justify-center rounded bg-white/10 hover:bg-white/15 text-white hover:text-cyan-200 text-xs font-semibold border border-white/5 transition-colors whitespace-nowrap focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                type="button"
              >
                <Clipboard size={13} className="mr-1.5 shrink-0" />
                Copy đường dẫn
              </button>
              <button
                disabled={!item.path}
                onClick={() => onRevealFile(item)}
                className="h-8 px-3 flex items-center justify-center rounded bg-white/10 hover:bg-white/15 text-white hover:text-cyan-200 text-xs font-semibold border border-white/5 transition-colors whitespace-nowrap focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                type="button"
              >
                <FolderOpen size={13} className="mr-1.5 shrink-0" />
                Mở vị trí
              </button>
              <button
                disabled={!hasCaption}
                onClick={() => onCopyCaption(item)}
                className="h-8 px-3 flex items-center justify-center rounded bg-white/10 hover:bg-white/15 text-white hover:text-cyan-200 text-xs font-semibold border border-white/5 transition-colors whitespace-nowrap focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                type="button"
              >
                <Captions size={13} className="mr-1.5 shrink-0" />
                Copy lời bình
              </button>
              <button
                onClick={() => onShowLog(item)}
                className="h-8 px-3 flex items-center justify-center rounded bg-white/10 hover:bg-white/15 text-white hover:text-cyan-200 text-xs font-semibold border border-white/5 transition-colors whitespace-nowrap focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
                type="button"
              >
                <FileSearch size={13} className="mr-1.5 shrink-0" />
                Xem nhật ký
              </button>
            </div>

            {/* Keyboard Shortcuts Help */}
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500 bg-slate-950/50 border border-white/5 rounded-md px-2.5 py-1.5 shadow-inner shrink-0">
              <Keyboard size={13} className="text-slate-400" />
              <span>Phím tắt:</span>
              <kbd className="bg-white/10 px-1 rounded text-white font-mono text-[9px] border border-white/5">A / ←</kbd>
              <span>Trước</span>
              <kbd className="bg-white/10 px-1 rounded text-white font-mono text-[9px] border border-white/5">D / →</kbd>
              <span>Sau</span>
              {selectionMode && (
                <>
                  <kbd className="bg-white/10 px-1 rounded text-white font-mono text-[9px] border border-white/5">Space / S</kbd>
                  <span>Chọn</span>
                </>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </GlassModal>
  );
}

function PathLine({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="min-w-0 rounded border border-white/5 bg-white/2 px-3 py-1.5">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mt-0.5 truncate text-xs text-slate-300 select-all" title={value}>
        {value}
      </div>
    </div>
  );
}
