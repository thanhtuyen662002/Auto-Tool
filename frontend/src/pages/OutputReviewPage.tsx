import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  getProject,
  getOutputReview,
  startRerender,
  updateOutputReview,
  videoFileUrl,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassPagination from '../components/glass/GlassPagination';
import { emitNotification } from '../components/notifications/NotificationProvider';
import NotifyOnChange from '../components/notifications/NotifyOnChange';
import WarningBox from '../components/WarningBox';
import type {
  OutputReviewItem,
  OutputReviewResponse,
  OutputReviewStatus,
  ProjectDetail,
  RerenderRequest,
} from '../types/project';

type FilterMode = 'all' | 'good' | 'warnings' | 'needs_rerender' | 'failed' | 'bad';

const FILTERS: Array<{ id: FilterMode; label: string }> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'good', label: 'Tốt' },
  { id: 'warnings', label: 'Có cảnh báo' },
  { id: 'needs_rerender', label: 'Cần render lại' },
  { id: 'failed', label: 'Bị lỗi' },
  { id: 'bad', label: 'Chưa đạt' },
];

export default function OutputReviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [review, setReview] = useState<OutputReviewResponse | null>(null);
  const [filter, setFilter] = useState<FilterMode>('all');
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [reuseScript, setReuseScript] = useState(true);
  const [reuseTimeline, setReuseTimeline] = useState(false);
  const [reuseSettings, setReuseSettings] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  useEffect(() => {
    if (!projectId) return;
    void loadReview(projectId);
  }, [projectId]);

  async function loadReview(activeProjectId = projectId, showMessage = false) {
    if (!activeProjectId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const [projectResult, response] = await Promise.all([
        getProject(activeProjectId),
        getOutputReview(activeProjectId),
      ]);
      setProject(projectResult);
      setReview(response);
      if (showMessage) setMessage('Đã làm mới đánh giá video đầu ra.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải đánh giá chất lượng video đầu ra.');
    } finally {
      setBusy(false);
    }
  }

  const filteredOutputs = useMemo(() => {
    const outputs = review?.outputs ?? [];
    return outputs.filter((output) => {
      if (filter === 'all') return true;
      if (filter === 'warnings') return output.warnings.length > 0;
      if (filter === 'failed') return output.status === 'failed' || output.recommended_action === 'rerender_failed';
      if (filter === 'needs_rerender') {
        return output.review_status === 'needs_rerender' || output.recommended_action === 'needs_rerender';
      }
      if (filter === 'bad') return output.review_status === 'bad' || output.recommended_action === 'bad';
      return output.recommended_action === filter || output.review_status === filter;
    });
  }, [filter, review?.outputs]);
  const totalPages = Math.ceil(filteredOutputs.length / pageSize);
  const pageStart = filteredOutputs.length ? (currentPage - 1) * pageSize + 1 : 0;
  const pageEnd = Math.min(currentPage * pageSize, filteredOutputs.length);
  const paginatedOutputs = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredOutputs.slice(start, start + pageSize);
  }, [currentPage, filteredOutputs]);
  const isDouyinProject = Boolean(
    project?.config.mode === 'douyin_reup'
      || project?.config.mode === 'silent_reup'
      || project?.config.douyin_reup,
  );

  useEffect(() => {
    setCurrentPage(1);
  }, [filter]);

  useEffect(() => {
    if (totalPages > 0 && currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  async function markOutput(outputIndex: number, status: OutputReviewStatus) {
    if (!projectId) return;
    setError(null);
    setMessage(null);
    try {
      await updateOutputReview(projectId, outputIndex, status);
      setReview((current) =>
        current
          ? {
              ...current,
              outputs: current.outputs.map((output) =>
                output.output_index === outputIndex ? { ...output, review_status: status } : output,
              ),
            }
          : current,
      );
      setMessage('Đã cập nhật đánh giá video.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể cập nhật đánh giá video đầu ra.');
    }
  }

  async function rerender(mode: RerenderRequest['mode']) {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const payload: RerenderRequest = {
        mode,
        output_indexes: mode === 'selected' ? Array.from(selected).sort((a, b) => a - b) : [],
        reuse_script: reuseScript,
        reuse_timeline: reuseTimeline,
        reuse_settings: reuseSettings,
      };
      const response = await startRerender(projectId, payload);
      navigate(`/queue/${projectId}/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể bắt đầu render lại.');
    } finally {
      setBusy(false);
    }
  }

  function toggleSelected(outputIndex: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(outputIndex)) {
        next.delete(outputIndex);
      } else {
        next.add(outputIndex);
      }
      return next;
    });
  }

  const summary = review?.summary;

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Đánh giá chất lượng video đầu ra</h1>
          <p className="mt-1 break-all text-sm text-muted">Dự án: {projectId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            disabled={busy}
            onClick={() => loadReview(projectId, true)}
          >
            Làm mới
          </button>
          <Link className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand" to="/">
            Tạo dự án mới
          </Link>
        </div>
      </div>

      <ApiErrorBox error={error} />
      <NotifyOnChange value={message} variant="success" />

      {summary ? <SummaryCards summary={summary} /> : null}

      <section className="mt-5 rounded-lg border border-line bg-white p-5 shadow-panel">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <h2 className="text-base font-semibold text-ink">Bộ lọc</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {FILTERS.map((item) => (
                <button
                  key={item.id}
                  className={`rounded-md border px-3 py-2 text-sm font-semibold ${
                    filter === item.id
                      ? 'border-brand bg-blue-50 text-brand'
                      : 'border-line bg-white text-ink hover:border-brand'
                  }`}
                  type="button"
                  onClick={() => setFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          {isDouyinProject ? (
          <div className="max-w-md rounded-md border border-cyan-200 bg-cyan-50 p-3 text-sm leading-6 text-cyan-900">
            Trang này chỉ dùng để xem điểm và đánh dấu thủ công. Với video Douyin Reup, hãy render lại từ trang kết quả bằng nút <span className="font-semibold">Chỉnh/render lại</span> để tool chạy đúng quy trình OCR, phụ đề, che sub và dựng video.
            <Link className="mt-2 inline-flex font-semibold text-cyan-700 hover:text-cyan-900" to="/results">
              Mở Tác vụ & Kết quả
            </Link>
          </div>
          ) : (
          <div className="grid gap-3 rounded-md bg-surface p-3 text-sm">
            <label className="flex items-center gap-2">
              <input className="h-4 w-4 accent-brand" type="checkbox" checked={reuseScript} onChange={(event) => setReuseScript(event.target.checked)} />
              <span>Dùng lại kịch bản</span>
            </label>
            <label className="flex items-center gap-2">
              <input className="h-4 w-4 accent-brand" type="checkbox" checked={reuseTimeline} onChange={(event) => setReuseTimeline(event.target.checked)} />
              <span>Dùng lại dòng thời gian</span>
            </label>
            <label className="flex items-center gap-2">
              <input className="h-4 w-4 accent-brand" type="checkbox" checked={reuseSettings} onChange={(event) => setReuseSettings(event.target.checked)} />
              <span>Dùng lại cài đặt</span>
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
                type="button"
                disabled={busy || selected.size === 0}
                onClick={() => rerender('selected')}
              >
                Render lại mục đã chọn
              </button>
              <button
                className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                type="button"
                disabled={busy}
                onClick={() => rerender('failed_only')}
              >
                Render lại video lỗi
              </button>
              <button
                className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand"
                type="button"
                disabled={busy}
                onClick={() => rerender('needs_rerender')}
              >
                Render lại video cần sửa
              </button>
            </div>
          </div>
          )}
        </div>
      </section>

      <section className="mt-5 space-y-4">
        {busy && !review ? (
          <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
            Đang tải đánh giá...
          </div>
        ) : null}
        {paginatedOutputs.map((output) => (
          <OutputReviewCard
            key={output.output_index}
            output={output}
            selected={selected.has(output.output_index)}
            allowSelection={!isDouyinProject}
            onToggleSelected={() => toggleSelected(output.output_index)}
            onMark={markOutput}
          />
        ))}
        {filteredOutputs.length ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-white px-4 py-3 text-sm text-muted shadow-panel">
            <span>
              Đang xem <span className="font-semibold text-ink">{pageStart}-{pageEnd}</span> / {filteredOutputs.length} video
            </span>
            <GlassPagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} className="mt-0" />
          </div>
        ) : null}
        {review && filteredOutputs.length === 0 ? (
          <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
            Không có video đầu ra nào khớp với bộ lọc này.
          </div>
        ) : null}
      </section>
    </main>
  );
}

function SummaryCards({ summary }: { summary: OutputReviewResponse['summary'] }) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
      <Metric label="Tổng số" value={summary.total_outputs} />
      <Metric label="Tốt" value={summary.good} />
      <Metric label="Cần xem lại" value={summary.review} />
      <Metric label="Cần render lại" value={summary.needs_rerender} />
      <Metric label="Bị lỗi" value={summary.failed} />
      <Metric label="Điểm trung bình" value={`${Math.round(summary.average_overall_score * 100)}%`} />
    </section>
  );
}

function OutputReviewCard({
  output,
  selected,
  allowSelection,
  onToggleSelected,
  onMark,
}: {
  output: OutputReviewItem;
  selected: boolean;
  allowSelection: boolean;
  onToggleSelected: () => void;
  onMark: (outputIndex: number, status: OutputReviewStatus) => void;
}) {
  const scoreRows = [
    ['Kỹ thuật', output.technical_score],
    ['Cảnh quay', output.segment_score],
    ['Âm thanh', output.audio_score],
    ['Phụ đề', output.subtitle_score],
    ['Dòng thời gian', output.timeline_score],
  ] as const;
  const videoSrc = output.video_path && output.video_path.toLowerCase().endsWith('.mp4') ? videoFileUrl(output.video_path) : null;

  return (
    <article className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
        <div>
          {videoSrc ? <video className="aspect-[9/16] max-h-[420px] w-full rounded-md bg-black" controls src={videoSrc} /> : null}
        </div>
        <div>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              {allowSelection ? (
                <label className="flex items-center gap-3">
                  <input className="h-4 w-4 accent-brand" type="checkbox" checked={selected} onChange={onToggleSelected} />
                  <span className="text-lg font-semibold text-ink">
                    Video {String(output.output_index).padStart(3, '0')}
                  </span>
                </label>
              ) : (
                <h2 className="text-lg font-semibold text-ink">Video {String(output.output_index).padStart(3, '0')}</h2>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusBadge value={output.status} />
                <StatusBadge value={output.recommended_action} />
                <StatusBadge value={output.review_status} />
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs font-medium text-muted">Điểm tổng thể</div>
              <div className="text-3xl font-semibold text-ink">{Math.round(output.overall_score * 100)}%</div>
            </div>
          </div>

          <div className="grid gap-3 text-sm sm:grid-cols-5">
            {scoreRows.map(([label, score]) => (
              <Metric key={label} label={label} value={`${Math.round(score * 100)}%`} />
            ))}
          </div>

          <WarningBox warnings={output.warnings} />
          {output.errors.length ? (
            <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {output.errors[0]}
            </div>
          ) : null}

          <div className="mt-4 break-all rounded-md bg-surface p-3 text-sm text-muted">{output.video_path}</div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button className="rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-brand" type="button" onClick={() => onMark(output.output_index, 'good')}>
              Đánh dấu tốt
            </button>
            <button className="rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-brand" type="button" onClick={() => onMark(output.output_index, 'bad')}>
              Đánh dấu chưa đạt
            </button>
            <button className="rounded-md border border-line bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-brand" type="button" onClick={() => onMark(output.output_index, 'needs_rerender')}>
              Cần render lại
            </button>
            <button className="rounded-md bg-brand px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" type="button" onClick={() => copy(output.video_path)}>
              Sao chép đường dẫn video
            </button>
            {output.errors.length ? (
              <button className="rounded-md border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-700 hover:border-red-400" type="button" onClick={() => copy(output.errors.join('\n'))}>
                Sao chép lỗi
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-white p-3 ring-1 ring-line">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold text-ink">{value}</div>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const classes =
    normalized.includes('failed') || normalized === 'bad'
      ? 'border-red-200 bg-red-50 text-red-700'
      : normalized.includes('rerender') || normalized === 'review' || normalized === 'warning'
        ? 'border-amber-200 bg-amber-50 text-amber-700'
        : 'border-emerald-200 bg-emerald-50 text-emerald-700';
  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${classes}`}>
      {formatStatus(value)}
    </span>
  );
}

function copy(value?: string | null) {
  if (!value) return;
  void navigator.clipboard.writeText(value);
  emitNotification({ variant: 'success', message: 'Đã sao chép.' });
}

function formatId(value: string) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatStatus(value: string) {
  const labels: Record<string, string> = {
    success: 'Thành công',
    warning: 'Có cảnh báo',
    failed: 'Thất bại',
    good: 'Tốt',
    bad: 'Chưa đạt',
    pending: 'Chưa đánh giá',
    ignored: 'Bỏ qua',
    review: 'Cần xem lại',
    needs_rerender: 'Cần render lại',
    rerender_failed: 'Render lại video lỗi',
  };
  return labels[value.toLowerCase()] ?? formatId(value);
}
