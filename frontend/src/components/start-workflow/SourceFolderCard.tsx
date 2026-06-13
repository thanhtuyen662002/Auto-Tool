import { Clipboard, FolderSearch, ScanSearch } from 'lucide-react';
import type { DouyinVideoItem } from '../../types/project';
import type { StartRecentFolder, StartScanSummary, StartWorkflowMode } from '../../types/startWorkflow';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import StartRecentFolders from './StartRecentFolders';

export default function SourceFolderCard({
  mode,
  value,
  onChange,
  onBrowse,
  onScan,
  onOpenBrowser,
  busy,
  scanSummary,
  videos,
  scanErrors,
  recentFolders,
  onUseRecent,
  onRemoveRecent,
}: {
  mode: StartWorkflowMode;
  value: string;
  onChange: (value: string) => void;
  onBrowse: () => void;
  onScan: () => void;
  onOpenBrowser?: () => void;
  busy: boolean;
  scanSummary: StartScanSummary | null;
  videos: DouyinVideoItem[];
  scanErrors: string[];
  recentFolders: StartRecentFolder[];
  onUseRecent: (path: string) => void;
  onRemoveRecent: (path: string) => void;
}) {
  const label = mode === 'silent_immersive' ? 'Chọn folder video' : 'Chọn folder video Douyin';
  const invalidFiles = scanSummary?.invalid ?? 0;
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start gap-3">
        <FolderSearch className="mt-1 shrink-0 text-cyan-200" size={22} />
        <div className="min-w-0">
          <h2 className="font-semibold text-white">{label}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            {mode === 'silent_immersive'
              ? 'Chọn folder chứa video không thoại hoặc chỉ có nhạc/tiếng thao tác.'
              : 'Chọn folder chứa video Douyin đã tải sẵn. Tool sẽ scan trước khi start.'}
          </p>
        </div>
      </div>

      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-200">Folder video</span>
        <input
          className="h-11 w-full rounded-md border border-white/15 bg-slate-950/80 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
          placeholder="D:/douyin/videos"
          spellCheck={false}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <GlassButton className="px-3" variant="secondary" onClick={onBrowse}>
          <FolderSearch size={16} />
          Browse
        </GlassButton>
        <GlassButton className="px-3" variant="ghost" onClick={() => void pastePath(onChange)}>
          <Clipboard size={16} />
          Paste path
        </GlassButton>
        <GlassButton className="px-3" variant="primary" loading={busy} disabled={!value.trim()} onClick={onScan}>
          <ScanSearch size={16} />
          Scan
        </GlassButton>
        {onOpenBrowser ? (
          <GlassButton className="px-3" variant="secondary" disabled={!value.trim()} onClick={onOpenBrowser}>
            <ScanSearch size={16} />
            Browser
          </GlassButton>
        ) : null}
      </div>

      {!value.trim() ? (
        <div className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-400">
          Chưa chọn folder video. Hãy chọn folder chứa video đã tải sẵn.
        </div>
      ) : null}
      {busy ? <div className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-100">Đang scan video...</div> : null}
      {scanSummary ? (
        <div className="grid gap-2 rounded-md border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
          <div className="font-semibold">Tìm thấy {scanSummary.valid} video hợp lệ.</div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <Metric label="Vertical" value={scanSummary.vertical} />
            <Metric label="Square" value={scanSummary.square} />
            <Metric label="Horizontal" value={scanSummary.horizontal} />
          </div>
          {invalidFiles ? <div className="text-xs text-amber-100">Có {invalidFiles} file không đọc được. Tool sẽ bỏ qua hoặc bạn có thể kiểm tra lại.</div> : null}
        </div>
      ) : null}
      {scanErrors.length ? (
        <div className="rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-sm leading-6 text-rose-100">
          {scanErrors.slice(0, 2).join(' ')}
        </div>
      ) : null}
      {scanSummary && !videos.length ? (
        <div className="rounded-md border border-amber-300/20 bg-amber-400/10 p-3 text-sm text-amber-100">
          Folder này chưa có video. Hãy thêm video .mp4/.mov/.mkv rồi scan lại.
        </div>
      ) : null}

      <StartRecentFolders folders={recentFolders} onRemove={onRemoveRecent} onUse={onUseRecent} />
    </GlassCard>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 p-2">
      <div className="font-semibold text-white">{value}</div>
      <div className="mt-1 text-slate-300">{label}</div>
    </div>
  );
}

async function pastePath(onChange: (value: string) => void) {
  try {
    const text = await navigator.clipboard.readText();
    if (text.trim()) onChange(text.trim());
  } catch {
    // Browser permissions can block clipboard reads; manual typing still works.
  }
}
