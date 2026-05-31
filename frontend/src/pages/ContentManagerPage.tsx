import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  exportProjectContent,
  getProject,
  getProjectContent,
  markContentCopied,
  markContentPosted,
  updateProjectContentItem,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import type {
  ContentBatchSummary,
  OutputContentItem,
  ProjectDetail,
  PublishStatus,
} from '../types/project';

type FilterValue = 'all' | PublishStatus;

interface EditableContent {
  hook: string;
  caption: string;
  hashtags: string;
  cta: string;
  platform: string;
  user_note: string;
}

const filters: Array<{ value: FilterValue; label: string }> = [
  { value: 'all', label: 'Tất cả' },
  { value: 'draft', label: 'Nháp' },
  { value: 'copied', label: 'Đã sao chép' },
  { value: 'posted', label: 'Đã đăng' },
  { value: 'skipped', label: 'Bỏ qua' },
];

const formatOptions = [
  { value: 'json', label: 'JSON' },
  { value: 'csv', label: 'CSV' },
  { value: 'txt', label: 'TXT' },
  { value: 'md', label: 'Markdown' },
];

export default function ContentManagerPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [items, setItems] = useState<OutputContentItem[]>([]);
  const [summary, setSummary] = useState<ContentBatchSummary | null>(null);
  const [drafts, setDrafts] = useState<Record<number, EditableContent>>({});
  const [filter, setFilter] = useState<FilterValue>('all');
  const [formats, setFormats] = useState<string[]>(['json', 'csv', 'txt', 'md']);
  const [exportedFiles, setExportedFiles] = useState<Array<{ format: string; path: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [busyIndex, setBusyIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    Promise.all([getProject(projectId), getProjectContent(projectId)])
      .then(([projectResult, contentResult]) => {
        setProject(projectResult);
        setItems(contentResult.items);
        setSummary(contentResult.summary);
        setDrafts(buildDrafts(contentResult.items));
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải nội dung đăng bài.'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const visibleItems = useMemo(() => {
    if (filter === 'all') return items;
    return items.filter((item) => item.publish_status === filter);
  }, [filter, items]);

  function updateDraft(outputIndex: number, patch: Partial<EditableContent>) {
    setDrafts((current) => ({
      ...current,
      [outputIndex]: {
        ...current[outputIndex],
        ...patch,
      },
    }));
  }

  async function saveItem(item: OutputContentItem, publishStatus?: PublishStatus) {
    if (!projectId) return;
    setBusyIndex(item.output_index);
    try {
      const draft = drafts[item.output_index];
      const response = await updateProjectContentItem(projectId, item.output_index, {
        hook: draft.hook,
        caption: draft.caption,
        hashtags: draft.hashtags,
        cta: draft.cta,
        platform: draft.platform,
        user_note: draft.user_note,
        publish_status: publishStatus,
      });
      applyUpdatedItem(response.item);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu caption.');
    } finally {
      setBusyIndex(null);
    }
  }

  async function copyAndMark(item: OutputContentItem) {
    if (!projectId) return;
    setBusyIndex(item.output_index);
    try {
      const draft = drafts[item.output_index];
      const text = [draft.caption.trim(), draft.hashtags.trim()].filter(Boolean).join('\n\n');
      await navigator.clipboard.writeText(text);
      const saved = await updateProjectContentItem(projectId, item.output_index, {
        hook: draft.hook,
        caption: draft.caption,
        hashtags: draft.hashtags,
        cta: draft.cta,
        platform: draft.platform,
        user_note: draft.user_note,
      });
      applyUpdatedItem(saved.item);
      const response = await markContentCopied(projectId, item.output_index);
      applyUpdatedItem(response.item);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể sao chép nội dung.');
    } finally {
      setBusyIndex(null);
    }
  }

  async function markPosted(item: OutputContentItem) {
    if (!projectId) return;
    setBusyIndex(item.output_index);
    try {
      const draft = drafts[item.output_index];
      const saved = await updateProjectContentItem(projectId, item.output_index, {
        hook: draft.hook,
        caption: draft.caption,
        hashtags: draft.hashtags,
        cta: draft.cta,
        platform: draft.platform,
        user_note: draft.user_note,
      });
      applyUpdatedItem(saved.item);
      const response = await markContentPosted(projectId, item.output_index, draft.platform);
      applyUpdatedItem(response.item);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đánh dấu đã đăng.');
    } finally {
      setBusyIndex(null);
    }
  }

  async function exportContent() {
    if (!projectId) return;
    try {
      const response = await exportProjectContent(projectId, formats);
      setExportedFiles(response.files);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể export nội dung.');
    }
  }

  function applyUpdatedItem(updated: OutputContentItem) {
    setItems((current) => {
      const next = current.map((item) => (item.output_index === updated.output_index ? updated : item));
      setSummary(buildSummary(next));
      return next;
    });
    setDrafts((current) => ({
      ...current,
      [updated.output_index]: toDraft(updated),
    }));
  }

  if (!projectId) {
    return <main className="mx-auto max-w-6xl px-6 py-6">Thiếu project_id.</main>;
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Quản lý caption</h1>
          <p className="mt-1 text-sm text-muted">
            {project?.config.project_name ?? projectId}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            to="/"
          >
            Tạo dự án mới
          </Link>
          <Link
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            to={projectId ? `/projects/${projectId}/review` : '/'}
          >
            Kiểm tra chất lượng
          </Link>
        </div>
      </div>

      <ApiErrorBox error={error} />

      {loading ? (
        <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
          Đang tải nội dung đăng bài...
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
          <section className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {filters.map((item) => (
                <button
                  key={item.value}
                  className={`rounded-md border px-4 py-2 text-sm font-semibold ${
                    filter === item.value
                      ? 'border-brand bg-blue-50 text-brand'
                      : 'border-line bg-white text-ink hover:border-brand'
                  }`}
                  type="button"
                  onClick={() => setFilter(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {visibleItems.length ? (
              visibleItems.map((item) => (
                <ContentCard
                  key={item.id}
                  item={item}
                  draft={drafts[item.output_index] ?? toDraft(item)}
                  busy={busyIndex === item.output_index}
                  onChange={(patch) => updateDraft(item.output_index, patch)}
                  onSave={() => saveItem(item)}
                  onCopy={() => copyAndMark(item)}
                  onPosted={() => markPosted(item)}
                  onSkip={() => saveItem(item, 'skipped')}
                />
              ))
            ) : (
              <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
                Chưa có nội dung phù hợp với bộ lọc hiện tại.
              </div>
            )}
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
              <h2 className="text-base font-semibold text-ink">Tổng quan</h2>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <SummaryBox label="Tổng" value={summary?.total_items ?? 0} />
                <SummaryBox label="Nháp" value={summary?.draft ?? 0} />
                <SummaryBox label="Đã sao chép" value={summary?.copied ?? 0} />
                <SummaryBox label="Đã đăng" value={summary?.posted ?? 0} />
                <SummaryBox label="Bỏ qua" value={summary?.skipped ?? 0} />
              </div>
            </section>

            <section className="rounded-lg border border-line bg-white p-5 shadow-panel">
              <h2 className="text-base font-semibold text-ink">Export</h2>
              <div className="mt-4 space-y-2">
                {formatOptions.map((option) => (
                  <label key={option.value} className="flex items-center gap-2 text-sm text-ink">
                    <input
                      className="h-4 w-4 rounded border-line text-brand"
                      type="checkbox"
                      checked={formats.includes(option.value)}
                      onChange={(event) => {
                        setFormats((current) =>
                          event.target.checked
                            ? [...current, option.value]
                            : current.filter((value) => value !== option.value),
                        );
                      }}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
              <button
                className="mt-4 w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                type="button"
                disabled={!formats.length}
                onClick={exportContent}
              >
                Export nội dung
              </button>
              {exportedFiles.length ? (
                <div className="mt-4 space-y-2 text-xs text-muted">
                  {exportedFiles.map((file) => (
                    <div key={`${file.format}-${file.path}`} className="break-all rounded-md bg-surface p-2">
                      <div className="font-semibold text-ink">{file.format}</div>
                      {file.path}
                    </div>
                  ))}
                </div>
              ) : null}
            </section>
          </aside>
        </div>
      )}
    </main>
  );
}

function ContentCard({
  item,
  draft,
  busy,
  onChange,
  onSave,
  onCopy,
  onPosted,
  onSkip,
}: {
  item: OutputContentItem;
  draft: EditableContent;
  busy: boolean;
  onChange: (patch: Partial<EditableContent>) => void;
  onSave: () => void;
  onCopy: () => void;
  onPosted: () => void;
  onSkip: () => void;
}) {
  return (
    <article className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold text-ink">Video {String(item.output_index).padStart(3, '0')}</h2>
            <StatusBadge status={item.publish_status} />
          </div>
          <p className="mt-1 break-all text-xs text-muted">{item.video_path}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50" type="button" disabled={busy} onClick={onSave}>
            Lưu
          </button>
          <button className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:opacity-50" type="button" disabled={busy} onClick={onCopy}>
            Copy
          </button>
          <button className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:opacity-50" type="button" disabled={busy} onClick={onPosted}>
            Đã đăng
          </button>
          <button className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 hover:border-amber-400 disabled:opacity-50" type="button" disabled={busy} onClick={onSkip}>
            Bỏ qua
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="block md:col-span-2">
          <span className="mb-1 block text-sm font-medium text-ink">Hook</span>
          <input
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            lang="vi"
            spellCheck
            value={draft.hook}
            onChange={(event) => onChange({ hook: event.target.value })}
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-1 block text-sm font-medium text-ink">Caption</span>
          <textarea
            className="min-h-28 w-full resize-y rounded-md border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            lang="vi"
            spellCheck
            value={draft.caption}
            onChange={(event) => onChange({ caption: event.target.value })}
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-1 block text-sm font-medium text-ink">Hashtags</span>
          <input
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            value={draft.hashtags}
            onChange={(event) => onChange({ hashtags: event.target.value })}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink">CTA</span>
          <input
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            lang="vi"
            spellCheck
            value={draft.cta}
            onChange={(event) => onChange({ cta: event.target.value })}
          />
        </label>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink">Nền tảng</span>
          <input
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            placeholder="TikTok, Shopee, Reels..."
            value={draft.platform}
            onChange={(event) => onChange({ platform: event.target.value })}
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-1 block text-sm font-medium text-ink">Ghi chú</span>
          <textarea
            className="min-h-20 w-full resize-y rounded-md border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-blue-100"
            lang="vi"
            spellCheck
            value={draft.user_note}
            onChange={(event) => onChange({ user_note: event.target.value })}
          />
        </label>
      </div>

      <div className="mt-4 grid gap-3 text-xs text-muted md:grid-cols-2">
        <Info label="Kiểu script" value={item.variant_style_id} />
        <Info label="Timeline" value={item.timeline_template_id} />
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: PublishStatus }) {
  const classes: Record<PublishStatus, string> = {
    draft: 'border-slate-200 bg-slate-50 text-slate-700',
    copied: 'border-blue-200 bg-blue-50 text-blue-700',
    posted: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    skipped: 'border-amber-200 bg-amber-50 text-amber-800',
  };
  const labels: Record<PublishStatus, string> = {
    draft: 'Nháp',
    copied: 'Đã sao chép',
    posted: 'Đã đăng',
    skipped: 'Bỏ qua',
  };
  return <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${classes[status]}`}>{labels[status]}</span>;
}

function SummaryBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="font-medium text-ink">{label}</div>
      <div className="mt-1 break-all">{value || '-'}</div>
    </div>
  );
}

function toDraft(item: OutputContentItem): EditableContent {
  return {
    hook: item.hook ?? '',
    caption: item.caption ?? '',
    hashtags: item.hashtags.join(' '),
    cta: item.cta ?? '',
    platform: item.platform ?? '',
    user_note: item.user_note ?? '',
  };
}

function buildDrafts(items: OutputContentItem[]): Record<number, EditableContent> {
  const result: Record<number, EditableContent> = {};
  for (const item of items) {
    result[item.output_index] = toDraft(item);
  }
  return result;
}

function buildSummary(items: OutputContentItem[]): ContentBatchSummary {
  return {
    total_items: items.length,
    draft: items.filter((item) => item.publish_status === 'draft').length,
    copied: items.filter((item) => item.publish_status === 'copied').length,
    posted: items.filter((item) => item.publish_status === 'posted').length,
    skipped: items.filter((item) => item.publish_status === 'skipped').length,
  };
}
