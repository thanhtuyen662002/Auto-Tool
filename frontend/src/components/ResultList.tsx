import { AlertTriangle, CheckCircle2, Clipboard, FileText, FolderOpen, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { videoFileUrl } from '../api/client';
import type { JobOutput } from '../types/project';
import GlassBadge, { type GlassBadgeVariant } from './glass/GlassBadge';
import GlassButton from './glass/GlassButton';
import GlassCard from './glass/GlassCard';
import GlassEmptyState from './glass/GlassEmptyState';
import { emitNotification } from './notifications/NotificationProvider';

interface ResultListProps {
  outputs: JobOutput[];
}

type Filter = 'all' | 'rendered' | 'warnings' | 'failed';

const filters: Array<{ value: Filter; label: string }> = [
  { value: 'all', label: 'Tất cả' },
  { value: 'rendered', label: 'Đã render' },
  { value: 'warnings', label: 'Cảnh báo' },
  { value: 'failed', label: 'Thất bại' },
];

export default function ResultList({ outputs }: ResultListProps) {
  const [filter, setFilter] = useState<Filter>('all');
  const visible = useMemo(() => outputs.filter((output) => matchesFilter(output, filter)), [filter, outputs]);

  if (!outputs.length) {
    return <GlassEmptyState title="Chưa có video đầu ra" message="Video hoàn tất sẽ xuất hiện tại đây cùng trạng thái render, cảnh báo và tệp liên quan." />;
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Lọc kết quả">
        {filters.map((item) => (
          <button
            key={item.value}
            className={`rounded-md border px-3 py-2 text-sm font-semibold transition ${filter === item.value ? 'border-cyan-300/45 bg-cyan-300/12 text-cyan-100' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'}`}
            type="button"
            onClick={() => setFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {visible.length ? (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {visible.map((output) => <ResultCard key={output.index} output={output} />)}
        </div>
      ) : (
        <GlassEmptyState title="Không có kết quả phù hợp" message="Đổi bộ lọc để xem các video ở trạng thái khác." />
      )}
    </div>
  );
}

function ResultCard({ output }: { output: JobOutput }) {
  const warnings = output.warnings ?? [];
  const errorText = shortText(output.error || output.errors?.[0] || '');
  const success = !errorText && !['failed', 'error'].includes(output.status.toLowerCase());
  const filename = output.path.split(/[\\/]/).pop() || `video-${output.index}.mp4`;
  const caption = captionWithHashtags(output);

  return (
    <GlassCard className="overflow-hidden" hover>
      <div className="relative aspect-video bg-black/45">
        {success && output.path ? (
          <video className="h-full w-full object-contain" controls preload="metadata" src={videoFileUrl(output.path)} />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-5 text-center text-rose-200">
            <XCircle size={30} />
            <span className="text-sm font-semibold">Không thể tạo bản xem trước</span>
          </div>
        )}
        <div className="pointer-events-none absolute left-3 top-3"><StatusBadge output={output} /></div>
      </div>

      <div className="grid gap-4 p-4">
        <div>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold text-white" title={filename}>{filename}</h2>
              <p className="mt-1 text-xs text-slate-400">Video {String(output.index).padStart(3, '0')} {output.duration ? `· ${output.duration.toFixed(1)}s` : ''}</p>
            </div>
            {success ? <CheckCircle2 className="shrink-0 text-emerald-300" size={18} /> : <AlertTriangle className="shrink-0 text-rose-300" size={18} />}
          </div>
          {errorText ? <p className="mt-3 rounded-md border border-rose-300/20 bg-rose-400/10 p-3 text-xs leading-5 text-rose-100">{errorText}</p> : null}
          {warnings.length ? <p className="mt-3 text-xs leading-5 text-amber-200">{warnings.length} cảnh báo. {shortText(warnings[0], 120)}</p> : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <GlassButton className="px-3" variant="secondary" title="Sao chép đường dẫn video" onClick={() => copy(output.path)}><Clipboard size={15} /> Sao chép đường dẫn</GlassButton>
          {caption ? <GlassButton className="px-3" variant="ghost" title="Sao chép lời bình và hashtag" onClick={() => copy(caption)}><FileText size={15} /> Lời bình</GlassButton> : null}
          <GlassButton className="px-3" variant="ghost" disabled={!output.log_file} title="Mở nhật ký xử lý" onClick={() => openLocalPath(output.log_file)}><FolderOpen size={15} /> Nhật ký</GlassButton>
        </div>

        <details className="border-t border-white/10 pt-3 text-xs text-slate-400">
          <summary className="cursor-pointer font-semibold text-slate-300">Chi tiết tệp</summary>
          <div className="mt-3 grid gap-2">
            <PathLine label="Video" value={output.path} />
            <PathLine label="Phụ đề" value={output.subtitle_ass_file ?? output.subtitle_file} />
            <PathLine label="Giọng đọc" value={output.voice_file} />
          </div>
        </details>
      </div>
    </GlassCard>
  );
}

function StatusBadge({ output }: { output: JobOutput }) {
  const normalized = output.status.toLowerCase();
  const warnings = output.warnings?.length ?? 0;
  let variant: GlassBadgeVariant = 'rendered';
  let label = 'Đã render';
  if (['failed', 'error'].includes(normalized)) { variant = 'failed'; label = 'Lỗi'; }
  else if (warnings || normalized === 'warning') { variant = 'warning'; label = 'Cảnh báo'; }
  else if (normalized === 'needs_review') { variant = 'needs_review'; label = 'Cần duyệt'; }
  return <GlassBadge variant={variant}>{label}</GlassBadge>;
}

function PathLine({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return <div className="grid grid-cols-[68px_minmax(0,1fr)] gap-2"><span>{label}</span><span className="truncate text-slate-300" title={value}>{value}</span></div>;
}

function matchesFilter(output: JobOutput, filter: Filter) {
  if (filter === 'all') return true;
  const status = output.status.toLowerCase();
  if (filter === 'failed') return ['failed', 'error'].includes(status);
  if (filter === 'warnings') return status === 'warning' || Boolean(output.warnings?.length);
  return !['failed', 'error', 'needs_review'].includes(status);
}

function copy(value?: string | null) {
  if (!value) return;
  void navigator.clipboard.writeText(value);
  emitNotification({ variant: 'success', message: 'Đã sao chép.' });
}

function captionWithHashtags(output: JobOutput): string {
  const caption = (output.caption ?? '').trim();
  const hashtags = (output.hashtags ?? []).join(' ').trim();
  return [caption, hashtags].filter(Boolean).join('\n\n');
}

function openLocalPath(path?: string | null) {
  if (!path) return;
  window.open(`file:///${encodeURI(path.replace(/\\/g, '/'))}`, '_blank');
}

function shortText(value: string, limit = 220) {
  const cleaned = value.replace(/\s+/g, ' ').trim();
  return cleaned.length <= limit ? cleaned : `${cleaned.slice(0, limit - 3)}...`;
}
