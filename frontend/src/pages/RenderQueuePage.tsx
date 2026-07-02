import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getJobStatus } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import QueueControlPanel from '../components/jobs/QueueControlPanel';
import QueueItemList from '../components/jobs/QueueItemList';
import RenderProgress from '../components/RenderProgress';
import { friendlyWarning } from '../components/WarningBox';
import {
  cancelQueueJob,
  getQueueState,
  moveQueueItemsToBottom,
  moveQueueItemsToTop,
  pauseQueueJob,
  prioritizeSelectedQueueItems,
  resumeQueueJob,
  retryFailedQueueItems,
  retrySelectedQueueItems,
  skipSelectedQueueItems,
} from '../services/queueControlApi';
import type { JobStatus, QueueActionResult, QueueState } from '../types/project';
import { loadProjectConfig } from '../utils/projectState';

const DONE_STATUSES = new Set(['completed', 'completed_with_errors', 'completed_with_warnings', 'failed', 'cancelled']);
const ADJUSTABLE_STATUSES = new Set(['paused', 'cancelled', 'failed', 'completed_with_errors', 'completed_with_warnings']);

export default function RenderQueuePage() {
  const { projectId, jobId } = useParams<{ projectId: string; jobId: string }>();
  const [job, setJob] = useState<JobStatus | null>(null);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<QueueActionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const projectName = useMemo(() => {
    if (job?.project_name) return job.project_name;
    if (!projectId) return 'Dự án';
    return loadProjectConfig(projectId)?.project_name ?? 'Dự án';
  }, [job?.project_name, projectId]);

  const load = useCallback(async () => {
    if (!jobId) return;
    try {
      const [nextJob, nextQueue] = await Promise.all([
        getJobStatus(jobId),
        getQueueState(jobId).catch(() => null),
      ]);
      setJob(nextJob);
      setQueue(nextQueue?.data ?? null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải trạng thái render.');
    }
  }, [jobId]);

  useEffect(() => {
    let mounted = true;
    async function guardedLoad() {
      if (!mounted) return;
      await load();
    }
    void guardedLoad();
    const interval = window.setInterval(() => {
      if (job?.status && DONE_STATUSES.has(job.status)) return;
      void guardedLoad();
    }, 2000);
    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, [job?.status, load]);

  useEffect(() => {
    if (!queue) return;
    setSelectedIds((current) => {
      const valid = new Set(queue.items.map((item) => item.id));
      const next = new Set([...current].filter((id) => valid.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [queue]);

  const canViewResults = Boolean(job?.status && DONE_STATUSES.has(job.status));
  const adjustAction = useMemo(() => buildAdjustAction(job, projectId, jobId), [job, jobId, projectId]);
  const canAdjustAndContinue = Boolean(
    adjustAction && jobId && ADJUSTABLE_STATUSES.has(String(queue?.status || job?.status || '')),
  );
  const selectedList = useMemo(() => [...selectedIds], [selectedIds]);

  async function runAction(name: string, action: () => Promise<QueueActionResult>) {
    setBusyAction(name);
    setError(null);
    try {
      const result = await action();
      setLastAction(result);
      setActionMessage(result.message);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thao tác hàng đợi thất bại.');
    } finally {
      setBusyAction(null);
    }
  }

  function toggleSelected(itemId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  function selectAllQueued() {
    if (!queue) return;
    setSelectedIds(
      new Set(
        queue.items
          .filter((item) => ['queued', 'failed', 'paused', 'skipped', 'cancelled'].includes(item.status))
          .map((item) => item.id),
      ),
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Hàng đợi render</h1>
          <p className="mt-1 text-sm text-muted">{projectName}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canAdjustAndContinue ? (
            <Link
              className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
              to={adjustAction?.to || '#'}
            >
              {adjustAction?.label || 'Mở cài đặt'}
            </Link>
          ) : null}
          {canViewResults ? (
          <Link
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            to={projectId ? `/results/${projectId}/${jobId}` : `/results/${jobId}`}
          >
            Xem kết quả
          </Link>
          ) : null}
        </div>
      </div>

      <div className="space-y-5">
        <ApiErrorBox error={error} />
        <RenderProgress job={job} />
        <QueueControlPanel
          queue={queue}
          selectedCount={selectedIds.size}
          busyAction={busyAction}
          actionMessage={actionMessage}
          lastResult={lastAction}
          onPause={() => jobId && runAction('pause', () => pauseQueueJob(jobId))}
          onResume={() => jobId && runAction('resume', () => resumeQueueJob(jobId))}
          onCancel={() => jobId && runAction('cancel', () => cancelQueueJob(jobId))}
          onRetryFailed={() => jobId && runAction('retryFailed', () => retryFailedQueueItems(jobId))}
          onRetrySelected={() => jobId && runAction('retrySelected', () => retrySelectedQueueItems(jobId, selectedList))}
          onSkipSelected={() => jobId && runAction('skipSelected', () => skipSelectedQueueItems(jobId, selectedList))}
          onPrioritizeSelected={() => jobId && runAction('prioritize', () => prioritizeSelectedQueueItems(jobId, selectedList))}
          onMoveToTop={() => jobId && runAction('top', () => moveQueueItemsToTop(jobId, selectedList))}
          onMoveToBottom={() => jobId && runAction('bottom', () => moveQueueItemsToBottom(jobId, selectedList))}
        />
        <BatchResourcePlanCard queue={queue} />
        <QueueItemList
          queue={queue}
          selectedIds={selectedIds}
          onToggle={toggleSelected}
          onSelectAllQueued={selectAllQueued}
          onClearSelection={() => setSelectedIds(new Set())}
        />

        <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-ink">Nhật ký</h2>
            {job?.logs_total ? (
              <span className="text-xs text-muted">
                Hiển thị {job.logs.length}/{job.logs_total} dòng mới nhất
              </span>
            ) : null}
          </div>
          {job?.logs_truncated ? (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Nhật ký rất dài nên màn hình chỉ tải phần mới nhất để tránh nặng giao diện. Log vẫn được lưu trong hệ thống.
            </div>
          ) : null}
          <div className="max-h-[420px] overflow-auto rounded-md bg-surface p-3 text-sm">
            {job?.logs?.length ? (
              job.logs.map((log, index) => (
                <div key={`${log.created_at}-${index}`} className="grid gap-2 border-b border-line py-2 last:border-0 md:grid-cols-[160px_90px_1fr]">
                  <span className="text-xs text-muted">{log.created_at}</span>
                  <span className="text-xs font-semibold uppercase text-ink">{formatLogLevel(log.level)}</span>
                  <span className="text-muted">{formatLogMessage(log.message)}</span>
                </div>
              ))
            ) : (
              <div className="text-muted">Đang chờ nhật ký render...</div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function BatchResourcePlanCard({ queue }: { queue: QueueState | null }) {
  const plan = queue?.concurrency_plan;
  if (!plan) return null;
  const resources = plan.resources || {};
  const cpu = typeof resources.cpu_count === 'number' ? resources.cpu_count : null;
  const ram = typeof resources.memory_total_gb === 'number' ? resources.memory_total_gb : null;
  const disk = typeof resources.disk_free_gb === 'number' ? resources.disk_free_gb : null;
  return (
    <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Kế hoạch tài nguyên batch</h2>
          <p className="mt-1 text-sm text-muted">
            Tool đang ưu tiên chạy ổn định cho batch lớn. Worker pool song song sẽ chỉ được bật khi scheduler an toàn sẵn sàng.
          </p>
        </div>
        <span className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-semibold text-muted">
          {plan.worker_pool_enabled ? 'Đa luồng' : 'Tuần tự an toàn'}
        </span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <ResourceMetric label="Yêu cầu" value={`${plan.requested_concurrency} luồng`} />
        <ResourceMetric label="Đang dùng" value={`${plan.effective_concurrency} luồng`} />
        <ResourceMetric label="Khuyến nghị máy" value={`${plan.recommended_concurrency} luồng`} />
        <ResourceMetric label="Tổng item" value={plan.total_items} />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <ResourceMetric label="Kích thước lô" value={`${plan.chunk_size || queue?.settings.batch_chunk_size || 0} video`} />
        <ResourceMetric label="Số lô" value={plan.chunk_count || 0} />
        <ResourceMetric label="Timeout FFmpeg" value={`${Math.round((queue?.settings.ffmpeg_timeout_seconds || 0) / 60)} phút`} />
        <ResourceMetric label="Watchdog" value={`${queue?.settings.watchdog_stale_minutes || 0} phút`} />
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <ResourceMetric label="Chế độ" value={queue?.settings.performance_mode === 'fast' ? 'Nhanh' : queue?.settings.performance_mode === 'balanced' ? 'Cân bằng' : 'An toàn'} />
        <ResourceMetric label="Tự dừng khi lỗi lặp" value={queue?.settings.pause_on_repeated_failures ? 'Bật' : 'Tắt'} />
        <ResourceMetric label="Ngưỡng lỗi liên tiếp" value={queue?.settings.max_consecutive_failures || 0} />
      </div>
      <div className="mt-4 grid gap-2 text-sm text-muted md:grid-cols-3">
        <div>CPU: {cpu ?? 'Không rõ'}</div>
        <div>RAM: {ram ? `${ram} GB` : 'Không rõ'}</div>
        <div>Ổ đĩa trống: {disk ? `${disk} GB` : 'Không rõ'}</div>
      </div>
      {plan.warnings.length || plan.reasons.length ? (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {[...plan.warnings, ...plan.reasons].slice(0, 4).map((item, index) => (
            <div key={`${item}-${index}`}>{item}</div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ResourceMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function buildAdjustAction(
  job: JobStatus | null,
  projectId: string | undefined,
  jobId: string | undefined,
): { label: string; to: string } | null {
  if (!projectId || !jobId) return null;
  const mode = resolveWorkflowMode(job, projectId);
  if (mode === 'douyin_reup') {
    return {
      label: 'Chỉnh cài đặt Reup rồi chạy tiếp',
      to: `/douyin-reup?job_id=${encodeURIComponent(jobId)}&resume=1`,
    };
  }
  if (mode === 'silent_reup') {
    return { label: 'Mở Silent Mode', to: '/silent-mode' };
  }
  if (mode === 'long_video') {
    return {
      label: 'Chỉnh Video dài/Phim rồi chạy tiếp',
      to: `/long-video-reup?job_id=${encodeURIComponent(jobId)}&resume=1`,
    };
  }
  if (mode === 'subtitle_render') {
    return { label: 'Mở kết quả sửa phụ đề', to: `/results/${projectId}/${jobId}` };
  }
  return { label: 'Mở cài đặt Affiliate', to: `/settings/${projectId}` };
}

function resolveWorkflowMode(job: JobStatus | null, projectId = ''): string {
  const mode = (job?.project_mode || '').toLowerCase();
  const normalizedProjectId = projectId.toLowerCase();
  const step = (job?.current_step || '').toLowerCase();
  if (mode) return mode;
  if ((job?.project_name || '').toLowerCase().includes('vlog dài')) return 'long_video';
  if (normalizedProjectId.startsWith('douyin_reup_') || step.startsWith('douyin_video_')) return 'douyin_reup';
  if (normalizedProjectId.startsWith('silent_')) return 'silent_reup';
  if (normalizedProjectId.startsWith('subtitle_review_') || step.startsWith('subtitle_review_')) return 'subtitle_render';
  return 'product_render';
}

function formatLogLevel(level: string): string {
  const labels: Record<string, string> = {
    info: 'Thông tin',
    warning: 'Cảnh báo',
    error: 'Lỗi',
  };
  return labels[level.toLowerCase()] ?? level;
}

function formatLogMessage(message: string): string {
  const warningMessage = friendlyWarning(message);
  if (warningMessage !== message) return warningMessage;

  const replacements: Array<[RegExp, string | ((match: RegExpMatchArray) => string)]> = [
    [/^Render job queued$/i, 'Tác vụ render đã được đưa vào hàng đợi.'],
    [/^Output folder:\s*(.*)$/i, (match) => `Thư mục đầu ra: ${match[1]}`],
    [/^Found\s+(\d+)\s+valid input videos$/i, (match) => `Tìm thấy ${match[1]} video nguồn hợp lệ.`],
    [/^Created\s+(\d+)\s+video segments$/i, (match) => `Đã tạo ${match[1]} cảnh cắt.`],
    [/^Rendering output\s+(\d+)$/i, (match) => `Đang render video ${match[1]}.`],
    [/^Project summary written:\s*(.*)$/i, (match) => `Đã ghi tổng kết dự án: ${match[1]}`],
    [/^No valid input videos found in\s*(.*)$/i, (match) => `Không tìm thấy video nguồn hợp lệ trong ${match[1]}`],
    [/^Render failed for output\s+(\d+):\s*(.*)$/i, (match) => `Render thất bại cho video ${match[1]}: ${match[2]}`],
  ];

  for (const [pattern, replacement] of replacements) {
    const match = message.match(pattern);
    if (!match) continue;
    return typeof replacement === 'string' ? replacement : replacement(match);
  }
  return message;
}
