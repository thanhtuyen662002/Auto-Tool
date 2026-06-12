import { Trash2 } from 'lucide-react';
import type { StartRecentFolder } from '../../types/startWorkflow';

export default function StartRecentFolders({
  folders,
  onUse,
  onRemove,
}: {
  folders: StartRecentFolder[];
  onUse: (path: string) => void;
  onRemove: (path: string) => void;
}) {
  return (
    <div className="grid gap-2">
      <div className="text-xs font-semibold uppercase tracking-normal text-slate-500">Gần đây</div>
      {folders.length ? (
        <div className="grid gap-2">
          {folders.slice(0, 5).map((folder) => (
            <div className="grid gap-2 rounded-md border border-white/10 bg-white/5 p-2 sm:grid-cols-[minmax(0,1fr)_auto]" key={folder.id}>
              <button className="truncate text-left text-xs text-slate-300 hover:text-cyan-200" type="button" title={folder.path} onClick={() => onUse(folder.path)}>
                {folder.path}
              </button>
              <div className="flex gap-1">
                <button className="rounded-md px-2 py-1 text-xs font-semibold text-cyan-200 hover:bg-white/10" type="button" onClick={() => onUse(folder.path)}>
                  Use
                </button>
                <button className="rounded-md p-1.5 text-slate-500 hover:bg-white/10 hover:text-rose-200" type="button" aria-label="Remove recent folder" onClick={() => onRemove(folder.path)}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs text-slate-500">Chưa có folder gần đây.</div>
      )}
    </div>
  );
}
