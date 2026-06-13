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
    if (!projectId) return 'Dự án';
    return loadProjectConfig(projectId)?.project_name ?? 'Dự án';
  }, [projectId]);

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
        {canViewResults ? (
          <Link
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            to={projectId ? `/results/${projectId}/${jobId}` : `/results/${jobId}`}
          >
            Xem kết quả
          </Link>
        ) : null}
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
        <QueueItemList
          queue={queue}
          selectedIds={selectedIds}
          onToggle={toggleSelected}
          onSelectAllQueued={selectAllQueued}
          onClearSelection={() => setSelectedIds(new Set())}
        />

        <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h2 className="mb-3 text-base font-semibold text-ink">Nhật ký</h2>
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
