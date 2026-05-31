import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getJobStatus } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import RenderProgress from '../components/RenderProgress';
import { friendlyWarning } from '../components/WarningBox';
import type { JobStatus } from '../types/project';
import { loadProjectConfig } from '../utils/projectState';

const DONE_STATUSES = new Set(['completed', 'completed_with_errors', 'failed']);

export default function RenderQueuePage() {
  const { projectId, jobId } = useParams<{ projectId: string; jobId: string }>();
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const projectName = useMemo(() => {
    if (!projectId) return 'Dự án';
    return loadProjectConfig(projectId)?.project_name ?? 'Dự án';
  }, [projectId]);

  useEffect(() => {
    if (!jobId) return;
    let mounted = true;

    async function load() {
      try {
        const nextJob = await getJobStatus(jobId!);
        if (!mounted) return;
        setJob(nextJob);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Không thể tải trạng thái render.');
      }
    }

    void load();
    const interval = window.setInterval(() => {
      if (job?.status && DONE_STATUSES.has(job.status)) return;
      void load();
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, [jobId, job?.status]);

  const canViewResults = Boolean(job?.status && DONE_STATUSES.has(job.status));

  return (
    <main className="mx-auto max-w-5xl px-6 py-6">
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

        <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <h2 className="mb-3 text-base font-semibold text-ink">Nhật ký</h2>
          <div className="max-h-[420px] overflow-auto rounded-md bg-surface p-3 text-sm">
            {job?.logs?.length ? (
              job.logs.map((log, index) => (
                <div key={`${log.created_at}-${index}`} className="grid gap-2 border-b border-line py-2 last:border-0 md:grid-cols-[160px_70px_1fr]">
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

  const simpleReplacements: Array<[RegExp, string | ((match: RegExpMatchArray) => string)]> = [
    [/^Render job queued$/i, 'Tác vụ render đã được đưa vào hàng đợi.'],
    [/^Rerender job queued for outputs:\s*(.*)$/i, (match) => `Tác vụ render lại đã được đưa vào hàng đợi cho video: ${match[1]}.`],
    [/^Output folder:\s*(.*)$/i, (match) => `Thư mục đầu ra: ${match[1]}`],
    [/^Found\s+(\d+)\s+valid input videos$/i, (match) => `Tìm thấy ${match[1]} video nguồn hợp lệ.`],
    [/^Created\s+(\d+)\s+video segments$/i, (match) => `Đã tạo ${match[1]} cảnh cắt.`],
    [
      /^Segment scoring completed:\s*(\d+)\s+usable,\s*(\d+)\s+rejected,\s*average=(.*)$/i,
      (match) => `Đã chấm điểm cảnh: ${match[1]} dùng được, ${match[2]} bị loại, điểm trung bình ${match[3]}.`,
    ],
    [/^Building product-aware timelines with template:\s*(.*)$/i, (match) => `Đang dựng dòng thời gian theo sản phẩm với mẫu: ${match[1]}.`],
    [/^Built\s+(\d+)\s+timelines$/i, (match) => `Đã dựng ${match[1]} dòng thời gian.`],
    [/^Rendering output\s+(\d+)$/i, (match) => `Đang render video ${match[1]}.`],
    [/^Project summary written:\s*(.*)$/i, (match) => `Đã ghi tổng kết dự án: ${match[1]}`],
    [/^Using project custom script; script variants are skipped\.$/i, 'Đang dùng kịch bản tuỳ chỉnh của dự án; bỏ qua biến thể kịch bản.'],
    [/^Script variant for output\s+(\d+):\s*(.*)$/i, (match) => `Biến thể kịch bản cho video ${match[1]}: ${match[2]}.`],
    [/^Script variants written:\s*(.*)$/i, (match) => `Đã ghi file biến thể kịch bản: ${match[1]}`],
    [/^Latest script saved from\s+(.*)$/i, (match) => `Đã lưu kịch bản mới nhất từ ${match[1]}`],
    [/^Could not save latest script from\s+(.*):\s*(.*)$/i, (match) => `Không thể lưu kịch bản mới nhất từ ${match[1]}: ${match[2]}`],
    [/^No valid input videos found in\s+(.*)$/i, (match) => `Không tìm thấy video nguồn hợp lệ trong ${match[1]}`],
    [/^No usable segments were created from the input videos\.$/i, 'Không tạo được cảnh cắt nào dùng được từ video nguồn.'],
    [/^No usable video segments after scoring$/i, 'Không còn cảnh cắt dùng được sau bước chấm điểm cảnh.'],
    [/^Render failed for output\s+(\d+):\s*(.*)$/i, (match) => `Render thất bại cho video ${match[1]}: ${match[2]}`],
  ];

  for (const [pattern, replacement] of simpleReplacements) {
    const match = message.match(pattern);
    if (!match) continue;
    return typeof replacement === 'string' ? replacement : replacement(match);
  }

  return message;
}
