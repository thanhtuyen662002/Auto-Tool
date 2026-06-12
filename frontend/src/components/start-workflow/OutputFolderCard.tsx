import { FolderOutput } from 'lucide-react';
import type { StartRecentFolder, StartWorkflowMode } from '../../types/startWorkflow';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import StartRecentFolders from './StartRecentFolders';

export default function OutputFolderCard({
  mode,
  outputFolder,
  projectName,
  onOutputFolderChange,
  onProjectNameChange,
  onBrowse,
  recentFolders,
  onUseRecent,
  onRemoveRecent,
}: {
  mode: StartWorkflowMode;
  outputFolder: string;
  projectName: string;
  onOutputFolderChange: (value: string) => void;
  onProjectNameChange: (value: string) => void;
  onBrowse: () => void;
  recentFolders: StartRecentFolder[];
  onUseRecent: (path: string) => void;
  onRemoveRecent: (path: string) => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start gap-3">
        <FolderOutput className="mt-1 shrink-0 text-emerald-300" size={22} />
        <div>
          <h2 className="font-semibold text-white">Chọn nơi lưu output</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">Tool sẽ kiểm tra quyền ghi khi bắt đầu xử lý.</p>
        </div>
      </div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-200">Output folder</span>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
          <input
            className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
            placeholder="D:/auto-tool/outputs"
            spellCheck={false}
            value={outputFolder}
            onChange={(event) => onOutputFolderChange(event.target.value)}
          />
          <GlassButton variant="secondary" onClick={onBrowse}>Browse</GlassButton>
        </div>
      </label>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-200">Project name</span>
        <input
          className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
          placeholder={mode === 'silent_immersive' ? 'silent_immersive_2026_06_12' : 'douyin_reup_2026_06_12'}
          value={projectName}
          onChange={(event) => onProjectNameChange(event.target.value)}
        />
      </label>
      {!outputFolder.trim() ? (
        <div className="rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-sm text-rose-100">Output folder không được rỗng.</div>
      ) : (
        <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs text-slate-400">
          Nếu folder chưa tồn tại, backend sẽ xử lý hoặc báo lỗi thân thiện khi start.
        </div>
      )}
      <StartRecentFolders folders={recentFolders} onRemove={onRemoveRecent} onUse={onUseRecent} />
    </GlassCard>
  );
}
