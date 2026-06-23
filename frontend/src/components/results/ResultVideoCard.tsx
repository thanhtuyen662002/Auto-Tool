import { Captions, Clipboard, Eye, FileSearch, FileText, FolderOpen, PlayCircle } from 'lucide-react';
import { thumbnailFileUrl } from '../../api/client';
import { captionBundle, type NormalizedResultItem, type ResultViewMode } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import ResultStatusBadges from './ResultStatusBadges';

export default function ResultVideoCard({
  item,
  selected,
  selectionMode,
  viewMode,
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
  viewMode: ResultViewMode;
  onToggleSelected: (item: NormalizedResultItem) => void;
  onPreview: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
}) {
  const hasCaption = Boolean(captionBundle(item));
  if (viewMode === 'compact') {
    return (
      <GlassCard className={`grid gap-3 p-3 ${selected ? 'border-cyan-300/60 bg-cyan-300/10' : ''}`}>
        <div className="grid gap-3 sm:grid-cols-[120px_minmax(0,1fr)_auto]">
          <PreviewTile item={item} compact onPreview={onPreview} />
          <CardBody item={item} compact />
          <CardActions
            hasCaption={hasCaption}
            item={item}
            selected={selected}
            selectionMode={selectionMode}
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
    <GlassCard className={`overflow-hidden ${selected ? 'border-cyan-300/60 bg-cyan-300/10' : ''}`} hover>
      <PreviewTile item={item} onPreview={onPreview} />
      <div className="grid gap-3 p-3">
        <CardBody item={item} />
        <CardActions
          hasCaption={hasCaption}
          item={item}
          selected={selected}
          selectionMode={selectionMode}
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
}: {
  item: NormalizedResultItem;
  compact?: boolean;
  onPreview: (item: NormalizedResultItem) => void;
}) {
  return (
    <button
      className={`group relative overflow-hidden bg-black/45 text-left ${compact ? 'aspect-video rounded-md' : 'aspect-video w-full'}`}
      type="button"
      onClick={() => onPreview(item)}
      aria-label={`Xem preview ${item.filename}`}
    >
      {item.path ? (
        <img
          alt=""
          className="h-full w-full object-cover opacity-85 transition group-hover:scale-[1.03] group-hover:opacity-100"
          loading="lazy"
          src={thumbnailFileUrl(item.path)}
        />
      ) : (
        <div className="flex h-full items-center justify-center text-slate-500">
          <FileText size={28} />
        </div>
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-black/15" />
      <div className="absolute left-3 top-3">
        <ResultStatusBadges item={item} />
      </div>
      <div className="absolute bottom-3 left-3 flex items-center gap-2 text-sm font-semibold text-white">
        <PlayCircle size={18} />
        Xem trước
      </div>
      <div className="absolute bottom-3 right-3 rounded-md bg-black/55 px-2 py-1 text-xs text-slate-200">{item.durationLabel}</div>
    </button>
  );
}

function CardBody({ item, compact }: { item: NormalizedResultItem; compact?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-white" title={item.filename}>
            {item.filename}
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Video {String(item.index).padStart(3, '0')} {item.presetName ? `· ${item.presetName}` : ''}
          </p>
        </div>
        {item.qaScorePercent != null ? <div className="shrink-0 text-sm font-semibold text-cyan-100">{item.qaScorePercent}%</div> : null}
      </div>
      {item.errorText ? <p className="mt-3 rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-xs leading-5 text-rose-100">{shortText(item.errorText, compact ? 120 : 180)}</p> : null}
      {!item.errorText && item.warnings.length ? <p className="mt-3 text-xs leading-5 text-amber-200">{shortText(item.warnings[0], compact ? 110 : 170)}</p> : null}
      {!compact && item.caption ? <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-300">{item.caption}</p> : null}
    </div>
  );
}

function CardActions({
  item,
  hasCaption,
  selected,
  selectionMode,
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
  onToggleSelected: (item: NormalizedResultItem) => void;
  onPreview: (item: NormalizedResultItem) => void;
  onCopyPath: (item: NormalizedResultItem) => void;
  onRevealFile: (item: NormalizedResultItem) => void;
  onCopyCaption: (item: NormalizedResultItem) => void;
  onShowLog: (item: NormalizedResultItem) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {selectionMode ? (
        <label className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-200">
          <input type="checkbox" checked={selected} disabled={!item.exportEligible} onChange={() => onToggleSelected(item)} />
          Chọn xuất
        </label>
      ) : null}
      <GlassButton className="px-3" variant="primary" disabled={!item.path} onClick={() => onPreview(item)}>
        <Eye size={15} />
        Xem
      </GlassButton>
      <GlassButton className="px-3" variant="secondary" disabled={!item.path} onClick={() => onCopyPath(item)}>
        <Clipboard size={15} />
        Đường dẫn
      </GlassButton>
      <GlassButton className="px-3" variant="ghost" disabled={!item.path} onClick={() => onRevealFile(item)}>
        <FolderOpen size={15} />
        Mở
      </GlassButton>
      <GlassButton className="px-3" variant="ghost" disabled={!hasCaption} onClick={() => onCopyCaption(item)}>
        <Captions size={15} />
        Lời bình
      </GlassButton>
      <GlassButton className="px-3" variant="ghost" disabled={!item.logFile && !item.files.length} onClick={() => onShowLog(item)}>
        <FileSearch size={15} />
        Nhật ký
      </GlassButton>
    </div>
  );
}

function shortText(value: string, limit: number) {
  const cleaned = value.replace(/\s+/g, ' ').trim();
  return cleaned.length <= limit ? cleaned : `${cleaned.slice(0, limit - 3)}...`;
}
