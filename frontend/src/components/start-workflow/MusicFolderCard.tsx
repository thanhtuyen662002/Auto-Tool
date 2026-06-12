import { Music2 } from 'lucide-react';
import type { StartRecentFolder } from '../../types/startWorkflow';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import StartRecentFolders from './StartRecentFolders';

export default function MusicFolderCard({
  musicFolder,
  addMusic,
  onMusicFolderChange,
  onAddMusicChange,
  onBrowse,
  recentFolders,
  onUseRecent,
  onRemoveRecent,
}: {
  musicFolder: string;
  addMusic: boolean;
  onMusicFolderChange: (value: string) => void;
  onAddMusicChange: (value: boolean) => void;
  onBrowse: () => void;
  recentFolders: StartRecentFolder[];
  onUseRecent: (path: string) => void;
  onRemoveRecent: (path: string) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start gap-3">
        <Music2 className="mt-1 shrink-0 text-violet-200" size={22} />
        <div>
          <h2 className="font-semibold text-white">Nhạc nền optional</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">Không chọn nhạc nền thì tool sẽ giữ âm thanh gốc nếu preset cho phép.</p>
        </div>
      </div>
      <label className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
        <input type="checkbox" checked={addMusic} onChange={(event) => onAddMusicChange(event.target.checked)} />
        <span>Thêm nhạc nền nhẹ</span>
      </label>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-200">Music folder</span>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <input
            className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
            placeholder="D:/music"
            spellCheck={false}
            value={musicFolder}
            onChange={(event) => onMusicFolderChange(event.target.value)}
          />
          <GlassButton variant="secondary" onClick={onBrowse}>Browse</GlassButton>
        </div>
      </label>
      {!musicFolder.trim() ? <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs text-slate-400">Chưa chọn nhạc nền. Tool vẫn có thể giữ âm thanh gốc.</div> : null}
      <StartRecentFolders folders={recentFolders} onRemove={onRemoveRecent} onUse={onUseRecent} />
    </GlassCard>
  );
}
