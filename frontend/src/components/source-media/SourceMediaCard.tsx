import { Eye, Music, Music2, Video } from 'lucide-react';
import type { SourceBrowserMediaItem, SourceBrowserPriority } from '../../types/project';
import { sourceMediaThumbnailUrl } from '../../services/sourceMediaApi';
import GlassButton from '../glass/GlassButton';
import SourceMediaQualityBadges from './SourceMediaQualityBadges';

export default function SourceMediaCard({
  item,
  folderId,
  selected,
  priority,
  onToggle,
  onPreview,
  onPriorityChange,
}: {
  item: SourceBrowserMediaItem;
  folderId: string;
  selected: boolean;
  priority: SourceBrowserPriority;
  onToggle: () => void;
  onPreview: () => void;
  onPriorityChange: (priority: SourceBrowserPriority) => void;
}) {
  return (
    <article className={selected ? 'rounded-md border border-cyan-300/50 bg-cyan-300/10 p-3' : 'rounded-md border border-white/10 bg-white/5 p-3'}>
      <button className="group relative block aspect-[9/16] w-full overflow-hidden rounded-md bg-slate-950/80 text-left" type="button" onClick={onToggle}>
        {item.thumbnail_path ? (
          <img className="h-full w-full object-cover" src={sourceMediaThumbnailUrl(folderId, item.id)} alt={item.filename} loading="lazy" />
        ) : (
          <div className="grid h-full place-items-center text-slate-500">
            <Video size={34} />
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-full bg-black/65 px-2 py-0.5 text-xs text-white">{formatDuration(item.duration_seconds)}</span>
        <span className="absolute right-2 top-2 rounded-full bg-black/65 p-1 text-white">
          {item.has_audio ? <Music2 size={14} /> : <Music size={14} />}
        </span>
        <span className={selected ? 'absolute inset-x-2 bottom-2 rounded-md bg-cyan-300 px-2 py-1 text-center text-xs font-semibold text-slate-950' : 'absolute inset-x-2 bottom-2 rounded-md bg-black/60 px-2 py-1 text-center text-xs text-white'}>
          {selected ? 'Đã chọn' : 'Bấm để chọn'}
        </span>
      </button>
      <div className="mt-3 grid gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-white" title={item.filename}>{item.filename}</div>
          <div className="mt-1 text-xs text-slate-400">{item.width || 0}x{item.height || 0} · {item.orientation}</div>
        </div>
        <SourceMediaQualityBadges item={item} />
        <div className="flex items-center gap-2">
          <select
            className="h-9 flex-1 rounded-md border border-white/15 bg-slate-950/80 px-2 text-xs text-white"
            value={priority}
            onChange={(event) => onPriorityChange(event.target.value as SourceBrowserPriority)}
          >
            <option value="high">Ưu tiên cao</option>
            <option value="normal">Bình thường</option>
            <option value="low">Ưu tiên thấp</option>
          </select>
          <GlassButton className="min-h-9 px-2 py-1" variant="ghost" onClick={onPreview}>
            <Eye size={15} />
          </GlassButton>
        </div>
      </div>
    </article>
  );
}

function formatDuration(value?: number | null): string {
  if (!value || value <= 0) return '0s';
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return minutes ? `${minutes}:${String(seconds).padStart(2, '0')}` : `${seconds}s`;
}
