import { AlertTriangle, Captions, Clipboard, Copy, Eye, FileSearch, FileText, FolderOpen, PlayCircle } from 'lucide-react';
import { thumbnailFileUrl } from '../../api/client';
import { captionBundle, type NormalizedResultItem, type ResultViewMode } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import ResultStatusBadges from './ResultStatusBadges';

export default function ResultVideoCard({
  item,
  selected,
  selectionMode,
  selectionLabel = 'Chọn xuất',
  viewMode,
  canSelectItem = (result) => result.exportEligible,
  onToggleSelected,
  onPreview,
  onCopyPath,
  onRevealFile,
  onCopyCaption,
  onShowLog,
}: {
  item: NormalizedResultItem;
  selected: boolean;
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
  const hasCaption = Boolean(captionBundle(item));
  const selectable = canSelectItem(item);

  if (viewMode === 'compact') {
    return (
      <GlassCard className={`relative border border-white/10 p-3 transition-all duration-300 hover:border-cyan-300/30 hover:shadow-[0_0_15px_rgba(34,211,238,0.05)] ${selected ? 'border-cyan-400/50 bg-cyan-950/20 shadow-[0_0_15px_rgba(34,211,238,0.1)]' : ''}`}>
        <div className="grid gap-3 sm:grid-cols-[140px_minmax(0,1fr)_auto] items-center">
          <PreviewTile item={item} compact onPreview={onPreview} selected={selected} selectionMode={selectionMode} selectable={selectable} onToggleSelected={onToggleSelected} />
          <CardBody item={item} compact />
          <CardActions
            hasCaption={hasCaption}
            item={item}
            selected={selected}
            selectionMode={selectionMode}
            selectionLabel={selectionLabel}
            canSelectItem={canSelectItem}
            onCopyCaption={onCopyCaption}
            onCopyPath={onCopyPath}
            onRevealFile={onRevealFile}
            onPreview={onPreview}
            onShowLog={onShowLog}
            onToggleSelected={onToggleSelected}
          />
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className={`flex flex-col overflow-hidden h-full border border-white/10 transition-all duration-300 hover:-translate-y-1 hover:border-cyan-300/30 hover:shadow-[0_4px_20px_rgba(0,0,0,0.4)] ${selected ? 'border-cyan-400/50 bg-cyan-950/20 shadow-[0_0_20px_rgba(34,211,238,0.08)]' : ''}`} hover>
      <PreviewTile item={item} onPreview={onPreview} selected={selected} selectionMode={selectionMode} selectable={selectable} onToggleSelected={onToggleSelected} />
      <div className="flex flex-col justify-between flex-1 p-4 gap-3 min-h-0">
        <CardBody item={item} />
        <CardActions
          hasCaption={hasCaption}
          item={item}
          selected={selected}
          selectionMode={selectionMode}
          selectionLabel={selectionLabel}
          canSelectItem={canSelectItem}
          onCopyCaption={onCopyCaption}
          onCopyPath={onCopyPath}
          onRevealFile={onRevealFile}
          onPreview={onPreview}
          onShowLog={onShowLog}
          onToggleSelected={onToggleSelected}
        />
      </div>
    </GlassCard>
  );
}

function PreviewTile({
  item,
  compact,
  onPreview,
  selected,
  selectionMode,
  selectable,
  onToggleSelected,
}: {
  item: NormalizedResultItem;
  compact?: boolean;
  onPreview: (item: NormalizedResultItem) => void;
  selected: boolean;
  selectionMode: boolean;
  selectable: boolean;
  onToggleSelected: (item: NormalizedResultItem) => void;
}) {
  return (
    <div className={`group relative overflow-hidden bg-black/50 ${compact ? 'aspect-video rounded-md w-[140px]' : 'aspect-video w-full'}`}>
      <button
        className="h-full w-full text-left focus:outline-none"
        type="button"
        onClick={() => onPreview(item)}
        aria-label={`Xem preview ${item.filename}`}
      >
        {item.path ? (
          <img
            alt=""
            className="h-full w-full object-cover opacity-75 transition duration-500 group-hover:scale-[1.04] group-hover:opacity-90"
            loading="lazy"
            src={thumbnailFileUrl(item.path)}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-slate-600 bg-slate-950/30">
            <FileText size={32} />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-black/30" />
        
        {/* Play Icon and Preview Text */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="flex items-center gap-1.5 rounded-full bg-cyan-500/90 px-3 py-1.5 text-xs font-semibold text-slate-950 shadow-lg transform translate-y-2 group-hover:translate-y-0 transition-transform duration-300">
            <PlayCircle size={14} />
            Xem ngay
          </div>
        </div>

        {/* Badges Overlay */}
        <div className="absolute left-2.5 top-2.5 flex flex-wrap gap-1 max-w-[80%] pointer-events-none">
          <ResultStatusBadges item={item} />
        </div>

        {/* Duration Overlay */}
        <div className="absolute bottom-2 right-2 rounded bg-black/75 px-1.5 py-0.5 text-[10px] font-medium text-slate-300 border border-white/5">
          {item.durationLabel}
        </div>
      </button>

      {/* Modern Top-Right Checkbox Overlay */}
      {selectionMode && (
        <div className="absolute right-2.5 top-2.5 z-10">
          <input
            type="checkbox"
            checked={selected}
            disabled={!selectable}
            onChange={() => onToggleSelected(item)}
            className="h-5 w-5 rounded border-white/20 bg-black/60 text-cyan-400 focus:ring-cyan-400/50 cursor-pointer disabled:cursor-not-allowed"
          />
        </div>
      )}
    </div>
  );
}

function CardBody({ item, compact }: { item: NormalizedResultItem; compact?: boolean }) {
  // Truncate the warning/error message neatly
  const errorMsg = item.errorText ? shortText(item.errorText, compact ? 100 : 130) : null;
  const warningMsg = !item.errorText && item.warnings.length ? shortText(item.warnings[0], compact ? 100 : 130) : null;

  return (
    <div className="flex flex-col min-w-0 flex-1 justify-between gap-2">
      <div className="min-w-0">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-sm font-semibold text-white truncate" title={item.filename}>
            {item.filename}
          </h2>
          {item.qaScorePercent != null && (
            <span className="shrink-0 rounded-full bg-cyan-950/50 border border-cyan-400/20 px-2 py-0.5 text-xs font-medium text-cyan-300">
              {item.qaScorePercent}%
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-slate-400">
          Video {String(item.index).padStart(3, '0')} {item.presetName ? `· ${item.presetName}` : ''}
        </p>
      </div>

      {/* Alert/Log block with fixed height to guarantee visual symmetry */}
      {!compact && (
        <div className="h-[74px] flex flex-col justify-center">
          {errorMsg ? (
            <div className="flex gap-2 rounded-md border border-rose-500/20 bg-rose-500/5 p-2 text-xs leading-4.5 text-rose-200 h-full overflow-hidden">
              <AlertTriangle className="mt-0.5 shrink-0 text-rose-400" size={14} />
              <div className="overflow-y-auto pr-1 select-text scrollbar-thin">{errorMsg}</div>
            </div>
          ) : warningMsg ? (
            <div className="flex gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-xs leading-4.5 text-amber-200 h-full overflow-hidden">
              <AlertTriangle className="mt-0.5 shrink-0 text-amber-400" size={14} />
              <div className="overflow-y-auto pr-1 select-text scrollbar-thin">{warningMsg}</div>
            </div>
          ) : item.caption ? (
            <p className="line-clamp-3 text-xs leading-5 text-slate-300 select-text font-normal italic pr-1 overflow-y-auto scrollbar-thin h-full">
              "{item.caption}"
            </p>
          ) : (
            <div className="flex items-center justify-center rounded-md border border-white/5 bg-white/2 h-full text-xs text-slate-500 italic">
              Không có nhật ký đặc biệt
            </div>
          )}
        </div>
      )}

      {compact && (errorMsg || warningMsg) && (
        <div className="text-xs leading-relaxed mt-1">
          {errorMsg && <span className="text-rose-400 font-medium">Lỗi: {errorMsg}</span>}
          {warningMsg && <span className="text-amber-400 font-medium">Cảnh báo: {warningMsg}</span>}
        </div>
      )}
    </div>
  );
}

function CardActions({
  item,
  hasCaption,
  selected,
  selectionMode,
  selectionLabel,
  canSelectItem,
  onToggleSelected,
  onPreview,
  onCopyPath,
  onRevealFile,
  onCopyCaption,
  onShowLog,
}: {
  item: NormalizedResultItem;
  hasCaption: boolean;
  selected: boolean;
  selectionMode: boolean;
  selectionLabel: string;
  canSelectItem: (item: NormalizedResultItem) => boolean;
  onToggleSelected: (item: NormalizedResultItem) => void;
  onPreview: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
}) {
  return (
    <div className="flex items-center justify-between mt-2 border-t border-white/5 pt-3 w-full">
      {/* Primary Action Button (Xem) */}
      <button
        className="h-8 px-3.5 flex items-center justify-center rounded bg-white/10 hover:bg-white/15 text-white hover:text-cyan-200 text-xs font-semibold transition-colors whitespace-nowrap focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
        disabled={!item.path}
        onClick={() => onPreview(item)}
      >
        <Eye size={13} className="mr-1.5 shrink-0" />
        Xem
      </button>

      {/* Secondary Actions Row */}
      <IconButton
        icon={<Clipboard size={13} />}
        title="Sao chép đường dẫn file video"
        disabled={!item.path}
        onClick={() => onCopyPath(item)}
      />
      <IconButton
        icon={<FolderOpen size={13} />}
        title="Mở vị trí chứa file trên máy"
        disabled={!item.path}
        onClick={() => onRevealFile(item)}
      />
      <IconButton
        icon={<Captions size={13} />}
        title="Sao chép lời bình/caption tiếng Việt"
        disabled={!hasCaption}
        onClick={() => onCopyCaption(item)}
      />
      <IconButton
        icon={<FileSearch size={13} />}
        title="Xem nhật ký hệ thống chi tiết"
        disabled={!item.logFile && !item.files.length}
        onClick={() => onShowLog(item)}
      />
    </div>
  );
}

function IconButton({
  icon,
  title,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="h-8 w-8 shrink-0 flex items-center justify-center rounded bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white border border-white/5 transition-all duration-200 disabled:opacity-30 disabled:hover:bg-white/5 disabled:hover:text-slate-400 disabled:cursor-not-allowed"
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={title}
    >
      {icon}
    </button>
  );
}

function shortText(value: string, limit: number) {
  const cleaned = value.replace(/\s+/g, ' ').trim();
  return cleaned.length <= limit ? cleaned : `${cleaned.slice(0, limit - 3)}...`;
}
