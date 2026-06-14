import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  applyProductDraftToProject,
  archiveProductDraft,
  attachProductDraftAssetsToProject,
  clearArchivedProductDrafts,
  createProjectFromDraft,
  deleteProductDraft,
  listProductDrafts,
  listProjects,
  updateProductDraft,
} from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassModal from '../components/glass/GlassModal';
import ProductDraftDetail from '../components/productDrafts/ProductDraftDetail';
import type {
  CreateProjectFromDraftRequest,
  ProductDraft,
  ProductDraftStatus,
  ProductDraftUpdateRequest,
  ProjectListItem,
} from '../types/project';

type StatusFilter = 'all' | ProductDraftStatus;
type SourceFilter = 'all' | 'shopee' | 'manual';
type DeleteConfirmState =
  | { kind: 'draft'; draftId: string; title: string }
  | { kind: 'archived'; count: number };

const STATUS_FILTERS: StatusFilter[] = ['all', 'new', 'reviewed', 'applied', 'archived'];
const SOURCE_FILTERS: SourceFilter[] = ['all', 'shopee', 'manual'];

export default function ImportInboxPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const draftIdFromUrl = searchParams.get('draft');
  const [drafts, setDrafts] = useState<ProductDraft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<ProductDraft | null>(null);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirmState | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [draftResponse, projectResponse] = await Promise.all([
        listProductDrafts({ limit: 200 }),
        listProjects(),
      ]);
      setDrafts(draftResponse.items);
      setProjects(projectResponse.items);
      setSelectedDraft((current) => {
        if (draftIdFromUrl) {
          const requested = draftResponse.items.find((draft) => draft.id === draftIdFromUrl);
          if (requested) return requested;
        }
        if (!current) return draftResponse.items[0] ?? null;
        return draftResponse.items.find((draft) => draft.id === current.id) ?? draftResponse.items[0] ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải Hộp thư Nhập sản phẩm.');
    } finally {
      setLoading(false);
    }
  }, [draftIdFromUrl]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filteredDrafts = useMemo(() => {
    return drafts.filter((draft) => {
      if (statusFilter !== 'all' && draft.status !== statusFilter) return false;
      if (sourceFilter === 'shopee' && draft.source.source_name !== 'shopee') return false;
      if (sourceFilter === 'manual' && draft.source.source_name === 'shopee') return false;
      return true;
    });
  }, [drafts, sourceFilter, statusFilter]);

  const summary = useMemo(
    () => ({
      total: drafts.length,
      new: drafts.filter((draft) => draft.status === 'new').length,
      reviewed: drafts.filter((draft) => draft.status === 'reviewed').length,
      applied: drafts.filter((draft) => draft.status === 'applied').length,
      archived: drafts.filter((draft) => draft.status === 'archived').length,
    }),
    [drafts],
  );

  async function runAction(action: () => Promise<void>, successMessage: string) {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thao tác thất bại.');
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveDraft(payload: ProductDraftUpdateRequest) {
    if (!selectedDraft) return;
    await runAction(async () => {
      const updated = await updateProductDraft(selectedDraft.id, payload);
      setSelectedDraft(updated);
    }, 'Đã lưu nháp.');
  }

  async function handleArchiveDraft(draftId: string) {
    await runAction(async () => {
      await archiveProductDraft(draftId);
    }, 'Đã lưu trữ nháp.');
  }

  function handleDeleteDraft(draftId: string) {
    const draft = drafts.find((item) => item.id === draftId);
    setDeleteConfirm({ kind: 'draft', draftId, title: draft?.title || 'bản nháp này' });
  }

  function handleClearArchived() {
    setDeleteConfirm({ kind: 'archived', count: summary.archived });
  }

  async function confirmDelete() {
    if (!deleteConfirm) return;
    if (deleteConfirm.kind === 'draft') {
      const draftId = deleteConfirm.draftId;
      await runAction(async () => {
        await deleteProductDraft(draftId);
        setSelectedDraft((current) => (current?.id === draftId ? null : current));
      }, 'Đã xóa nháp.');
    } else {
      await runAction(async () => {
        await clearArchivedProductDrafts();
      }, 'Đã dọn dẹp các bản nháp lưu trữ.');
    }
    setDeleteConfirm(null);
  }

  async function handleApply(projectId: string, selectedAssetIds: string[] = []) {
    if (!selectedDraft) return;
    await runAction(async () => {
      await applyProductDraftToProject(selectedDraft.id, projectId);
      if (selectedAssetIds.length > 0) {
        await attachProductDraftAssetsToProject(selectedDraft.id, projectId, selectedAssetIds);
      }
    }, selectedAssetIds.length > 0 ? 'Đã áp dụng bản nháp và tài nguyên đã chọn vào dự án.' : 'Đã áp dụng bản nháp vào dự án.');
  }

  async function handleCreateProject(payload: CreateProjectFromDraftRequest) {
    if (!selectedDraft) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await createProjectFromDraft(selectedDraft.id, payload);
      navigate(`/settings/${response.project_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo dự án từ bản nháp.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Hộp thư Nhập sản phẩm</h1>
          <p className="mt-1 text-sm text-muted">Sản phẩm được gửi từ Chrome Extension hoặc nhập thủ công.</p>
        </div>
        <div className="flex gap-2">
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
            type="button"
            onClick={refresh}
          >
            Làm mới
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-red-600 hover:border-red-400"
            type="button"
            onClick={handleClearArchived}
          >
            Xóa lưu trữ
          </button>
        </div>
      </div>

      <ApiErrorBox error={error} />
      {message ? <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">{message}</div> : null}

      <section className="mb-5 grid gap-3 sm:grid-cols-5">
        <SummaryCard label="Tổng nháp" value={summary.total} />
        <SummaryCard label="Mới" value={summary.new} />
        <SummaryCard label="Đã xem" value={summary.reviewed} />
        <SummaryCard label="Đã áp dụng" value={summary.applied} />
        <SummaryCard label="Đã lưu trữ" value={summary.archived} />
      </section>

      <section className="mb-5 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((status) => (
          <FilterButton key={status} active={statusFilter === status} onClick={() => setStatusFilter(status)}>
            {status === 'all' ? 'Tất cả' : status === 'new' ? 'Mới' : status === 'reviewed' ? 'Đã xem' : status === 'applied' ? 'Đã áp dụng' : 'Đã lưu trữ'}
          </FilterButton>
        ))}
        <span className="mx-1 h-9 w-px bg-line" />
        {SOURCE_FILTERS.map((source) => (
          <FilterButton key={source} active={sourceFilter === source} onClick={() => setSourceFilter(source)}>
            {source === 'all' ? 'Tất cả nguồn' : source === 'shopee' ? 'Shopee Extension' : 'Thủ công (Manual)'}
          </FilterButton>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(300px,0.42fr)_minmax(0,0.58fr)]">
        <section className="space-y-3">
          {loading ? <p className="rounded-lg border border-line bg-white p-5 text-sm text-muted">Đang tải bản nháp...</p> : null}
          {!loading && filteredDrafts.length === 0 ? (
            <p className="rounded-lg border border-line bg-white p-5 text-sm text-muted">Không tìm thấy bản nháp nào khớp với bộ lọc.</p>
          ) : null}
          {filteredDrafts.map((draft) => (
            <DraftCard
              key={draft.id}
              draft={draft}
              selected={selectedDraft?.id === draft.id}
              onView={() => setSelectedDraft(draft)}
              onArchive={() => handleArchiveDraft(draft.id)}
              onDelete={() => handleDeleteDraft(draft.id)}
            />
          ))}
        </section>

        {selectedDraft ? (
          <ProductDraftDetail
            draft={selectedDraft}
            projects={projects}
            saving={saving}
            onSave={handleSaveDraft}
            onApplyToProject={handleApply}
            onCreateProject={handleCreateProject}
            onArchive={() => handleArchiveDraft(selectedDraft.id)}
          />
        ) : (
          <section className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
            Chọn một bản nháp để xem chi tiết.
          </section>
        )}
      </div>

      <GlassModal
        open={deleteConfirm !== null}
        title={deleteConfirm?.kind === 'archived' ? 'Xác nhận xóa nháp lưu trữ' : 'Xác nhận xóa bản nháp'}
        onClose={() => {
          if (!saving) setDeleteConfirm(null);
        }}
      >
        <div className="space-y-4">
          {deleteConfirm?.kind === 'archived' ? (
            <>
              <p className="text-sm leading-6 text-slate-200">
                Bạn có chắc chắn muốn xóa vĩnh viễn {deleteConfirm.count} bản nháp đã lưu trữ?
              </p>
              <p className="rounded-md border border-amber-300/25 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-100">
                Hành động này chỉ xóa các bản nháp đang ở trạng thái lưu trữ và không thể hoàn tác.
              </p>
            </>
          ) : (
            <>
              <p className="text-sm leading-6 text-slate-200">
                Bạn có chắc chắn muốn xóa vĩnh viễn bản nháp <strong>{deleteConfirm?.title}</strong>?
              </p>
              <p className="rounded-md border border-rose-300/25 bg-rose-300/10 px-3 py-2 text-xs leading-5 text-rose-100">
                Sau khi xóa, dữ liệu sản phẩm đã nhập từ Shopee Extension sẽ không còn trong Hộp thư Nhập.
              </p>
            </>
          )}
          <div className="flex flex-wrap justify-end gap-3 pt-2">
            <button
              className="rounded-md border border-white/15 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              disabled={saving}
              onClick={() => setDeleteConfirm(null)}
            >
              Hủy bỏ
            </button>
            <button
              className="rounded-md bg-rose-500 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              disabled={saving}
              onClick={() => void confirmDelete()}
            >
              {saving ? 'Đang xóa...' : 'Xác nhận xóa'}
            </button>
          </div>
        </div>
      </GlassModal>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-panel">
      <div className="text-xs font-semibold uppercase text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function FilterButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`rounded-md px-3 py-2 text-sm font-semibold ${
        active ? 'bg-brand text-white' : 'border border-line bg-white text-ink hover:border-brand'
      }`}
      type="button"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function DraftCard({
  draft,
  selected,
  onView,
  onArchive,
  onDelete,
}: {
  draft: ProductDraft;
  selected: boolean;
  onView: () => void;
  onArchive: () => void;
  onDelete: () => void;
}) {
  const warnings = draft.validation_issues.filter((issue) => issue.severity !== 'info').length;
  return (
    <article className={`rounded-lg border bg-white p-4 shadow-panel ${selected ? 'border-brand' : 'border-line'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-ink">{draft.title}</h2>
          <p className="mt-1 text-xs text-muted">Nguồn: {draft.source.source_name === 'shopee' ? 'Shopee Extension' : 'Thủ công'}</p>
        </div>
        <span className="rounded bg-surface px-2 py-1 text-xs font-semibold uppercase text-muted">
          {draft.status === 'new' ? 'Mới' : draft.status === 'reviewed' ? 'Đã xem' : draft.status === 'applied' ? 'Đã dùng' : draft.status === 'archived' ? 'Đã lưu trữ' : draft.status}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <InfoItem label="Độ tin cậy" value={`${Math.round(draft.confidence_score * 100)}%`} />
        <InfoItem label="Ngành hàng" value={draft.industry_preset_id ?? 'Chưa cấu hình'} />
        <InfoItem label="Ngày nhập" value={formatDate(draft.source.imported_at)} />
        <InfoItem label="Cảnh báo" value={String(warnings)} />
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="rounded-md bg-brand px-3 py-2 text-xs font-semibold text-white" type="button" onClick={onView}>
          Xem
        </button>
        {draft.source.source_url ? (
          <a className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" href={draft.source.source_url} rel="noreferrer" target="_blank">
            Mở link gốc
          </a>
        ) : null}
        <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-ink hover:border-brand" type="button" onClick={onArchive}>
          Lưu trữ
        </button>
        <button className="rounded-md border border-line bg-white px-3 py-2 text-xs font-semibold text-red-600 hover:border-red-400" type="button" onClick={onDelete}>
          Xóa
        </button>
      </div>
    </article>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-semibold text-muted">{label}</dt>
      <dd className="mt-0.5 truncate text-ink">{value}</dd>
    </div>
  );
}

function titleCase(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}
