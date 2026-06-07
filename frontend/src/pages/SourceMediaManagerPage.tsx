import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  bulkUpdateSegmentReview,
  getSourceMedia,
  getSourceSegments,
  thumbnailFileUrl,
  updateSegmentReview,
  updateSourceMediaReview,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import type {
  MediaReviewStatus,
  SegmentReviewItem,
  SegmentReviewStatus,
  SourceMediaItem,
  SourceMediaResponse,
} from '../types/project';

type SegmentFilter = 'all' | 'usable' | 'rejected' | 'favorite' | 'excluded' | 'low_score' | 'high_score';
type SegmentSort = 'score_desc' | 'score_asc' | 'time' | 'duration';

const SEGMENT_FILTERS: Array<{ id: SegmentFilter; label: string }> = [
  { id: 'all', label: 'Tất cả' },
  { id: 'usable', label: 'Dùng được' },
  { id: 'rejected', label: 'Bị loại kỹ thuật' },
  { id: 'favorite', label: 'Favorite' },
  { id: 'excluded', label: 'Excluded' },
  { id: 'low_score', label: 'Score thấp' },
  { id: 'high_score', label: 'Score cao' },
];

export default function SourceMediaManagerPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [sourceMedia, setSourceMedia] = useState<SourceMediaResponse | null>(null);
  const [segments, setSegments] = useState<SegmentReviewItem[]>([]);
  const [selectedMedia, setSelectedMedia] = useState<SourceMediaItem | null>(null);
  const [selectedSegments, setSelectedSegments] = useState<Set<string>>(() => new Set());
  const [filter, setFilter] = useState<SegmentFilter>('all');
  const [sort, setSort] = useState<SegmentSort>('score_desc');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    void loadSourceMedia(projectId);
  }, [projectId]);

  async function loadSourceMedia(activeProjectId = projectId) {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getSourceMedia(activeProjectId);
      setSourceMedia(response);
      if (!selectedMedia && response.items.length) {
        setSelectedMedia(response.items[0]);
        await loadSegments(activeProjectId, response.items[0].path);
      } else if (selectedMedia) {
        const nextSelected = response.items.find((item) => item.path === selectedMedia.path) ?? response.items[0] ?? null;
        setSelectedMedia(nextSelected);
        if (nextSelected) await loadSegments(activeProjectId, nextSelected.path);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải source media.');
    } finally {
      setLoading(false);
    }
  }

  async function loadSegments(activeProjectId: string, sourcePath: string) {
    const response = await getSourceSegments(activeProjectId, { sourcePath });
    setSegments(response.items);
    setSelectedSegments(new Set());
  }

  async function selectMedia(item: SourceMediaItem) {
    if (!projectId) return;
    setSelectedMedia(item);
    setError(null);
    try {
      await loadSegments(projectId, item.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải segment của video nguồn.');
    }
  }

  async function markMedia(item: SourceMediaItem, status: MediaReviewStatus) {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await updateSourceMediaReview(projectId, item.path, status);
      setSourceMedia((current) =>
        current
          ? {
              ...current,
              items: current.items.map((media) => (media.path === item.path ? response.item : media)),
            }
          : current,
      );
      if (selectedMedia?.path === item.path) setSelectedMedia(response.item);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể cập nhật trạng thái video nguồn.');
    } finally {
      setBusy(false);
    }
  }

  async function markSegment(segmentId: string, status: SegmentReviewStatus) {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const response = await updateSegmentReview(projectId, segmentId, status);
      setSegments((current) => current.map((item) => (item.segment_id === segmentId ? response.item : item)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể cập nhật trạng thái segment.');
    } finally {
      setBusy(false);
    }
  }

  async function bulkMark(status: SegmentReviewStatus, ids?: string[]) {
    if (!projectId) return;
    const targetIds = ids ?? Array.from(selectedSegments);
    if (!targetIds.length) return;
    setBusy(true);
    setError(null);
    try {
      await bulkUpdateSegmentReview(projectId, targetIds, status);
      if (selectedMedia) await loadSegments(projectId, selectedMedia.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể cập nhật hàng loạt segment.');
    } finally {
      setBusy(false);
    }
  }

  async function excludeLowScore() {
    const lowScoreIds = segments.filter((item) => item.overall_score < 0.45).map((item) => item.segment_id);
    if (!lowScoreIds.length) return;
    if (!window.confirm('Loại tất cả segment có score dưới 0.45?')) return;
    await bulkMark('excluded', lowScoreIds);
  }

  function toggleSegment(segmentId: string) {
    setSelectedSegments((current) => {
      const next = new Set(current);
      if (next.has(segmentId)) next.delete(segmentId);
      else next.add(segmentId);
      return next;
    });
  }

  const visibleSegments = useMemo(() => {
    const filtered = segments.filter((item) => {
      if (filter === 'usable') return !item.reject_reasons.length && item.review_status !== 'excluded';
      if (filter === 'rejected') return item.reject_reasons.length > 0;
      if (filter === 'favorite') return item.review_status === 'favorite';
      if (filter === 'excluded') return item.review_status === 'excluded';
      if (filter === 'low_score') return item.overall_score < 0.45;
      if (filter === 'high_score') return item.overall_score >= 0.75;
      return true;
    });
    return [...filtered].sort((a, b) => {
      if (sort === 'score_asc') return a.overall_score - b.overall_score;
      if (sort === 'time') return a.start - b.start;
      if (sort === 'duration') return b.duration - a.duration;
      return b.overall_score - a.overall_score;
    });
  }, [filter, segments, sort]);

  const summary = sourceMedia?.summary;

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Source Media Manager</h1>
          <p className="mt-1 break-all text-sm text-muted">Dự án: {projectId}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            disabled={loading || busy}
            onClick={() => void loadSourceMedia()}
          >
            Làm mới
          </button>
          <Link
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            to={projectId ? `/settings/${projectId}` : '/'}
          >
            Quay lại render
          </Link>
        </div>
      </div>

      <ApiErrorBox error={error} />

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <Metric label="Total videos" value={summary.total_media} />
          <Metric label="Excluded videos" value={summary.excluded_media} />
          <Metric label="Total segments" value={summary.total_segments} />
          <Metric label="Usable segments" value={summary.usable_segments} />
          <Metric label="Favorite" value={summary.favorite_segments} />
          <Metric label="Average score" value={formatPercent(summary.average_segment_score)} />
        </div>
      ) : null}

      <div className="mt-5 grid gap-5 lg:grid-cols-[420px_1fr]">
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-ink">Video nguồn</h2>
          {loading ? <PanelText text="Đang tải danh sách video nguồn..." /> : null}
          {sourceMedia?.items.map((item) => (
            <MediaCard
              item={item}
              key={item.path}
              selected={selectedMedia?.path === item.path}
              busy={busy}
              onSelect={() => void selectMedia(item)}
              onMark={(status) => void markMedia(item, status)}
            />
          ))}
          {!loading && !sourceMedia?.items.length ? <PanelText text="Chưa có video nguồn hợp lệ." /> : null}
        </section>

        <section className="space-y-4">
          <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-ink">Segment</h2>
                <p className="mt-1 break-all text-sm text-muted">
                  {selectedMedia ? selectedMedia.filename : 'Chọn một video nguồn để xem segment.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" disabled={busy || !selectedSegments.size} type="button" onClick={() => void bulkMark('excluded')}>
                  Exclude selected
                </button>
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" disabled={busy || !selectedSegments.size} type="button" onClick={() => void bulkMark('favorite')}>
                  Mark favorite
                </button>
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" disabled={busy || !selectedSegments.size} type="button" onClick={() => void bulkMark('good')}>
                  Mark good
                </button>
                <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand disabled:text-muted" disabled={busy || !selectedSegments.size} type="button" onClick={() => void bulkMark('pending')}>
                  Reset pending
                </button>
                <button className="rounded-md border border-red-200 bg-white px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:text-muted" disabled={busy || !segments.length} type="button" onClick={() => void excludeLowScore()}>
                  Exclude low score
                </button>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {SEGMENT_FILTERS.map((item) => (
                <button
                  className={`rounded-md border px-3 py-2 text-sm font-semibold ${
                    filter === item.id ? 'border-brand bg-blue-50 text-brand' : 'border-line bg-white text-ink hover:border-brand'
                  }`}
                  key={item.id}
                  type="button"
                  onClick={() => setFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
              <select
                className="rounded-md border border-line bg-white px-3 py-2 text-sm text-ink"
                value={sort}
                onChange={(event) => setSort(event.target.value as SegmentSort)}
              >
                <option value="score_desc">Score cao nhất</option>
                <option value="score_asc">Score thấp nhất</option>
                <option value="time">Thời gian trong video</option>
                <option value="duration">Duration</option>
              </select>
            </div>
          </div>

          <div className="grid gap-3">
            {visibleSegments.map((item) => (
              <SegmentCard
                item={item}
                key={item.segment_id}
                selected={selectedSegments.has(item.segment_id)}
                busy={busy}
                onToggle={() => toggleSegment(item.segment_id)}
                onMark={(status) => void markSegment(item.segment_id, status)}
              />
            ))}
            {selectedMedia && !visibleSegments.length ? <PanelText text="Không có segment phù hợp bộ lọc hiện tại." /> : null}
          </div>
        </section>
      </div>
    </main>
  );
}

function MediaCard({
  item,
  selected,
  busy,
  onSelect,
  onMark,
}: {
  item: SourceMediaItem;
  selected: boolean;
  busy: boolean;
  onSelect: () => void;
  onMark: (status: MediaReviewStatus) => void;
}) {
  return (
    <article className={`rounded-lg border bg-white p-4 shadow-panel ${selected ? 'border-brand' : 'border-line'}`}>
      <button className="w-full text-left" type="button" onClick={onSelect}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="break-all text-sm font-semibold text-ink">{item.filename}</h3>
            <p className="mt-1 text-xs text-muted">
              {item.duration.toFixed(1)}s • {item.width}x{item.height} • {formatOrientation(item.orientation)}
            </p>
          </div>
          <StatusBadge status={item.review_status} />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          <Metric label="Score" value={formatPercent(item.quality_score)} compact />
          <Metric label="Usable" value={item.usable_segment_count} compact />
          <Metric label="Rejected" value={item.rejected_segment_count} compact />
        </div>
        {item.review_status === 'excluded' ? (
          <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            Excluded - sẽ không dùng khi render.
          </p>
        ) : null}
      </button>
      <div className="mt-3 flex flex-wrap gap-2">
        <ActionButton disabled={busy} label="Mark Good" onClick={() => onMark('good')} />
        <ActionButton disabled={busy} label="Exclude" onClick={() => onMark('excluded')} />
        <ActionButton disabled={busy} label="Mark Bad" onClick={() => onMark('bad')} />
        <ActionButton disabled={busy} label="Favorite" onClick={() => onMark('favorite')} />
      </div>
    </article>
  );
}

function SegmentCard({
  item,
  selected,
  busy,
  onToggle,
  onMark,
}: {
  item: SegmentReviewItem;
  selected: boolean;
  busy: boolean;
  onToggle: () => void;
  onMark: (status: SegmentReviewStatus) => void;
}) {
  return (
    <article className="rounded-lg border border-line bg-white p-4 shadow-panel">
      <div className="grid gap-4 md:grid-cols-[150px_1fr]">
        <div className="aspect-video overflow-hidden rounded-md bg-surface">
          {item.preview_thumbnail_path ? (
            <img className="h-full w-full object-cover" alt="Segment thumbnail" src={thumbnailFileUrl(item.preview_thumbnail_path)} />
          ) : (
            <div className="flex h-full items-center justify-center px-3 text-center text-xs text-muted">Không có thumbnail</div>
          )}
        </div>
        <div>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <label className="flex items-start gap-3">
              <input className="mt-1 h-4 w-4 accent-brand" type="checkbox" checked={selected} onChange={onToggle} />
              <span>
                <span className="block font-semibold text-ink">
                  Segment {item.start.toFixed(1)}s → {item.end.toFixed(1)}s
                </span>
                <span className="mt-1 block text-xs text-muted">
                  Duration {item.duration.toFixed(1)}s • Score {formatPercent(item.overall_score)}
                  {item.crop_safety_score != null ? ` • Crop ${formatPercent(item.crop_safety_score)}` : ''}
                </span>
              </span>
            </label>
            <StatusBadge status={item.review_status} />
          </div>
          <div className="mt-3 flex flex-wrap gap-1">
            {item.tags.map((tag) => (
              <span className="rounded bg-surface px-2 py-1 text-xs text-muted" key={tag}>
                {tag}
              </span>
            ))}
          </div>
          {item.reject_reasons.length ? (
            <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Lý do loại kỹ thuật: {item.reject_reasons.join(', ')}
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <ActionButton disabled={busy} label="Favorite" onClick={() => onMark('favorite')} />
            <ActionButton disabled={busy} label="Good" onClick={() => onMark('good')} />
            <ActionButton disabled={busy} label="Exclude" onClick={() => onMark('excluded')} />
            <ActionButton disabled={busy} label="Bad" onClick={() => onMark('bad')} />
            <ActionButton disabled={busy} label="Pending" onClick={() => onMark('pending')} />
          </div>
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: number | string; compact?: boolean }) {
  return (
    <div className="rounded-md bg-white p-3 shadow-sm">
      <div className="text-xs text-muted">{label}</div>
      <div className={`${compact ? 'text-sm' : 'text-lg'} font-semibold text-ink`}>{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: MediaReviewStatus | SegmentReviewStatus }) {
  const className =
    status === 'excluded' || status === 'bad'
      ? 'border-red-200 bg-red-50 text-red-700'
      : status === 'favorite'
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : status === 'good'
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
          : 'border-line bg-surface text-muted';
  return <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${className}`}>{status}</span>;
}

function ActionButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      className="rounded-md border border-line bg-white px-3 py-1.5 text-xs font-semibold text-ink hover:border-brand disabled:text-muted"
      disabled={disabled}
      type="button"
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function PanelText({ text }: { text: string }) {
  return <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">{text}</div>;
}

function formatPercent(value?: number | null): string {
  if (value == null) return '-';
  return `${Math.round(value * 100)}%`;
}

function formatOrientation(value: string): string {
  const labels: Record<string, string> = {
    vertical: 'Dọc',
    horizontal: 'Ngang',
    square: 'Vuông',
  };
  return labels[value] ?? value;
}
