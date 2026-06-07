import type { JobStatus } from '../types/project';

interface RenderProgressProps {
  job: JobStatus | null;
}

export default function RenderProgress({ job }: RenderProgressProps) {
  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));
  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-ink">{formatStep(job?.current_step ?? 'queued')}</div>
          <div className="text-xs text-muted">{formatStatus(job?.status ?? 'queued')}</div>
        </div>
        <div className="text-xl font-semibold text-brand">{progress}%</div>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-surface">
        <div className="h-full bg-brand transition-all" style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div className="rounded-md bg-surface p-3">
          <div className="text-xs text-muted">Đã hoàn thành</div>
          <div className="font-semibold">{job?.completed_outputs ?? 0}</div>
        </div>
        <div className="rounded-md bg-surface p-3">
          <div className="text-xs text-muted">Bị lỗi</div>
          <div className="font-semibold">{job?.failed_outputs ?? 0}</div>
        </div>
        <div className="rounded-md bg-surface p-3">
          <div className="text-xs text-muted">Tổng số</div>
          <div className="font-semibold">{job?.total_outputs ?? 0}</div>
        </div>
      </div>
      {job?.cache_summary ? (
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-md bg-emerald-50 p-3 text-emerald-700">
            <div className="text-xs">Cache hit</div>
            <div className="font-semibold">{job.cache_summary.hits ?? 0}</div>
          </div>
          <div className="rounded-md bg-amber-50 p-3 text-amber-800">
            <div className="text-xs">Cache miss</div>
            <div className="font-semibold">{job.cache_summary.misses ?? 0}</div>
          </div>
          <div className="rounded-md bg-surface p-3">
            <div className="text-xs text-muted">Dung lượng cache</div>
            <div className="font-semibold">{formatCacheSize(job.cache_summary.cache_size_mb ?? 0)}</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatCacheSize(sizeMb: number): string {
  if (sizeMb >= 1024) return `${(sizeMb / 1024).toFixed(2)} GB`;
  return `${sizeMb.toFixed(1)} MB`;
}

function formatStatus(status: string): string {
  const normalized = status.toLowerCase();
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    running: 'Đang chạy',
    completed: 'Hoàn thành',
    completed_with_errors: 'Hoàn thành nhưng có lỗi',
    failed: 'Thất bại',
  };
  return labels[normalized] ?? status;
}

function formatStep(step: string): string {
  const normalized = step.toLowerCase();
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    starting: 'Đang bắt đầu',
    scanning_media: 'Đang quét video nguồn',
    creating_segments: 'Đang tạo cảnh cắt',
    scoring_segments: 'Đang chấm điểm cảnh',
    building_timelines: 'Đang dựng dòng thời gian',
    preparing_rerender: 'Đang chuẩn bị render lại',
    building_rerender_timelines: 'Đang dựng dòng thời gian render lại',
    completed: 'Hoàn thành',
    failed: 'Thất bại',
  };
  if (normalized.startsWith('rendering_video_')) {
    return `Đang render video ${normalized.replace('rendering_video_', '')}`;
  }
  if (normalized.startsWith('rerendering_video_')) {
    return `Đang render lại video ${normalized.replace('rerendering_video_', '')}`;
  }
  return labels[normalized] ?? step;
}
