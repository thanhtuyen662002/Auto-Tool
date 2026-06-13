import { RefreshCw, ScanSearch } from 'lucide-react';
import GlassButton from '../glass/GlassButton';

export default function SourceMediaToolbar({
  folderPath,
  recursive,
  generateThumbnails,
  busy,
  hasResult,
  onRecursiveChange,
  onGenerateThumbnailsChange,
  onScan,
  onRescan,
}: {
  folderPath: string;
  recursive: boolean;
  generateThumbnails: boolean;
  busy: boolean;
  hasResult: boolean;
  onRecursiveChange: (value: boolean) => void;
  onGenerateThumbnailsChange: (value: boolean) => void;
  onScan: () => void;
  onRescan: () => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-white/10 bg-white/5 p-3">
      <div>
        <div className="text-xs font-semibold uppercase text-slate-500">Folder nguồn</div>
        <div className="mt-1 truncate text-sm text-white" title={folderPath}>{folderPath || 'Chưa chọn folder'}</div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
        <label className="inline-flex items-center gap-2">
          <input className="h-4 w-4 accent-cyan-300" type="checkbox" checked={recursive} onChange={(event) => onRecursiveChange(event.target.checked)} />
          Scan thư mục con
        </label>
        <label className="inline-flex items-center gap-2">
          <input className="h-4 w-4 accent-cyan-300" type="checkbox" checked={generateThumbnails} onChange={(event) => onGenerateThumbnailsChange(event.target.checked)} />
          Tạo thumbnail
        </label>
        <GlassButton className="ml-auto px-3" variant="primary" loading={busy} disabled={!folderPath.trim()} onClick={hasResult ? onRescan : onScan}>
          {hasResult ? <RefreshCw size={16} /> : <ScanSearch size={16} />}
          {hasResult ? 'Scan lại' : 'Scan media'}
        </GlassButton>
      </div>
    </div>
  );
}
