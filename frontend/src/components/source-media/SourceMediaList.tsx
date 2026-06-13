import { Eye } from 'lucide-react';
import type { SourceBrowserMediaItem, SourceBrowserPriority } from '../../types/project';
import GlassButton from '../glass/GlassButton';
import SourceMediaQualityBadges from './SourceMediaQualityBadges';

export default function SourceMediaList({
  items,
  selectedIds,
  priorities,
  onToggle,
  onPreview,
  onPriorityChange,
}: {
  items: SourceBrowserMediaItem[];
  selectedIds: Set<string>;
  priorities: Record<string, SourceBrowserPriority>;
  onToggle: (id: string) => void;
  onPreview: (item: SourceBrowserMediaItem) => void;
  onPriorityChange: (id: string, priority: SourceBrowserPriority) => void;
}) {
  return (
    <div className="overflow-hidden rounded-md border border-white/10">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-white/5 text-xs uppercase text-slate-400">
          <tr>
            <th className="p-3">Chọn</th>
            <th className="p-3">File</th>
            <th className="p-3">Thông số</th>
            <th className="p-3">Đánh giá</th>
            <th className="p-3">Priority</th>
            <th className="p-3" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-t border-white/10 text-slate-200">
              <td className="p-3">
                <input className="h-4 w-4 accent-cyan-300" type="checkbox" checked={selectedIds.has(item.id)} onChange={() => onToggle(item.id)} />
              </td>
              <td className="max-w-xs p-3">
                <div className="truncate font-medium text-white" title={item.filename}>{item.filename}</div>
                <div className="truncate text-xs text-slate-500" title={item.path}>{item.path}</div>
              </td>
              <td className="p-3 text-xs text-slate-400">
                <div>{item.width || 0}x{item.height || 0}</div>
                <div>{Math.round(item.duration_seconds || 0)}s · {item.has_audio ? 'Có audio' : 'Không audio'}</div>
              </td>
              <td className="p-3">
                <SourceMediaQualityBadges item={item} />
              </td>
              <td className="p-3">
                <select
                  className="h-9 rounded-md border border-white/15 bg-slate-950/80 px-2 text-xs text-white"
                  value={priorities[item.id] || item.priority || 'normal'}
                  onChange={(event) => onPriorityChange(item.id, event.target.value as SourceBrowserPriority)}
                >
                  <option value="high">Cao</option>
                  <option value="normal">Thường</option>
                  <option value="low">Thấp</option>
                </select>
              </td>
              <td className="p-3 text-right">
                <GlassButton className="min-h-9 px-2 py-1" variant="ghost" onClick={() => onPreview(item)}>
                  <Eye size={15} />
                </GlassButton>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
