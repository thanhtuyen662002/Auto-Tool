import { Clapperboard, RefreshCw, Sparkles } from 'lucide-react';
import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassButton from '../components/glass/GlassButton';
import GlassPagination from '../components/glass/GlassPagination';
import NotifyOnChange from '../components/notifications/NotifyOnChange';
import ExportPackPanel, { type ExportPackOptions, type ExportScope } from '../components/results/ExportPackPanel';
import ResultQAPanel from '../components/results/ResultQAPanel';
import ResultRetryPanel from '../components/results/ResultRetryPanel';
import ResultTechnicalLogDrawer from '../components/results/ResultTechnicalLogDrawer';
import ResultVideoGrid from '../components/results/ResultVideoGrid';
import ResultVideoPreviewModal from '../components/results/ResultVideoPreviewModal';
import ResultsEmptyState from '../components/results/ResultsEmptyState';
import ResultsFilterBar from '../components/results/ResultsFilterBar';
import ResultsLayout from '../components/results/ResultsLayout';
import ResultsSkeleton from '../components/results/ResultsSkeleton';
import ResultsSummaryCards from '../components/results/ResultsSummaryCards';
import WorkflowStepper from '../components/workflow/WorkflowStepper';
import {
  createResultsExportPack,
  fetchResultsView,
  openResultsExportPack,
  retryFailedResults,
  runFinalQA,
} from '../services/resultsApi';
import { openFolder, revealFile } from '../services/localAppApi';
import type { DouyinReupSummary, JobOutput, JobStatus, PlatformExportPack, PlatformTarget } from '../types/project';
import {
  captionBundle,
  copyText,
  filterAndSortResults,
  normalizeResultOutput,
  summarizeResults,
  type NormalizedResultItem,
  type ResultFilter,
  type ResultSort,
  type ResultViewMode,
} from '../utils/resultStatus';

const FINAL_JOB_STATUSES = new Set(['completed', 'completed_with_errors', 'failed']);

export default function ResultPage() {
  const { projectId, jobId } = useParams<{ projectId?: string; jobId?: string }>();
  const navigate = useNavigate();
  const [outputs, setOutputs] = useState<JobOutput[]>([]);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [douyinSummary, setDouyinSummary] = useState<DouyinReupSummary | null>(null);
  const [exportPack, setExportPack] = useState<PlatformExportPack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<'qa' | 'export' | 'retry' | 'open' | null>(null);
  const [filter, setFilter] = useState<ResultFilter>('all');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<ResultSort>('index_asc');
  const [viewMode, setViewMode] = useState<ResultViewMode>('grid');
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [platformTarget, setPlatformTarget] = useState<PlatformTarget>('tiktok');
  const [exportScope, setExportScope] = useState<ExportScope>('include_warnings');
  const [exportOptions, setExportOptions] = useState<ExportPackOptions>({
    copy_videos: true,
    include_subtitles: true,
    include_logs: true,
    include_captions: true,
    include_posting_checklist: true,
  });
  const [previewItem, setPreviewItem] = useState<NormalizedResultItem | null>(null);
  const [logItem, setLogItem] = useState<NormalizedResultItem | null>(null);
  const [logOpen, setLogOpen] = useState(false);

  const loadResults = useCallback(
    async (quiet = false) => {
      if (!jobId) return;
      if (!quiet) setLoading(true);
      try {
        const view = await fetchResultsView(jobId);
        setOutputs(view.outputs);
        setJobStatus(view.jobStatus);
        setDouyinSummary(view.douyinSummary);
        setExportPack(view.exportPack);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không thể tải kết quả job.');
      } finally {
        if (!quiet) setLoading(false);
      }
    },
    [jobId],
  );

  useEffect(() => {
    void loadResults();
  }, [loadResults]);

  const jobRunning = Boolean(jobStatus && !FINAL_JOB_STATUSES.has(jobStatus.status));
  useEffect(() => {
    if (!jobId || !jobRunning) return undefined;
    const timer = window.setInterval(() => void loadResults(true), 4000);
    return () => window.clearInterval(timer);
  }, [jobId, jobRunning, loadResults]);

  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    setCurrentPage(1);
  }, [filter, search, sort]);

  const items = useMemo(() => outputs.map(normalizeResultOutput), [outputs]);
  const visibleItems = useMemo(() => filterAndSortResults(items, filter, search, sort), [filter, items, search, sort]);
  const totalPages = Math.ceil(visibleItems.length / pageSize);
  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return visibleItems.slice(start, start + pageSize);
  }, [visibleItems, currentPage, pageSize]);
  const selectedCount = useMemo(() => items.filter((item) => selectedIds.has(item.id)).length, [items, selectedIds]);
  const summary = useMemo(() => summarizeResults(items, selectedCount), [items, selectedCount]);
  const failedItems = useMemo(() => items.filter((item) => item.health === 'failed' || item.qaStatus === 'failed'), [items]);
  const exportOutputIndexes = useMemo(
    () => getExportOutputIndexes(items, selectedIds, exportScope),
    [exportScope, items, selectedIds],
  );

  useEffect(() => {
    setSelectedIds((current) => {
      const validIds = new Set(items.map((item) => item.id));
      const next = new Set([...current].filter((id) => validIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [items]);

  function toggleSelected(item: NormalizedResultItem) {
    if (!item.exportEligible) return;
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      return next;
    });
  }

  function selectAllEligible() {
    setSelectedIds(new Set(items.filter((item) => item.exportEligible).map((item) => item.id)));
  }

  async function copyPath(item: NormalizedResultItem) {
    await copyText(item.path);
    setActionMessage(`Đã copy path: ${item.filename}`);
  }

  async function copyCaption(item: NormalizedResultItem) {
    await copyText(captionBundle(item));
    setActionMessage(`Đã copy caption: ${item.filename}`);
  }

  async function revealResult(item: NormalizedResultItem) {
    if (!item.path) return;
    setError(null);
    try {
      await revealFile(item.path);
      setActionMessage(`Đã mở vị trí file: ${item.filename}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở vị trí file.');
    }
  }

  function showLog(item: NormalizedResultItem) {
    setLogItem(item);
    setLogOpen(true);
  }

  async function handleRunQA() {
    if (!jobId) return;
    setBusyAction('qa');
    setError(null);
    setActionMessage(null);
    try {
      const response = await runFinalQA(jobId, platformTarget);
      await loadResults(true);
      setActionMessage(`Final QA đã check ${response.summary.total_checked} output.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể chạy Final QA cho job này.');
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateExportPack() {
    if (!jobId) return;
    setBusyAction('export');
    setError(null);
    setActionMessage(null);
    try {
      const response = await createResultsExportPack(jobId, {
        platform_target: platformTarget,
        output_dir: null,
        ...exportOptions,
        output_indexes: exportOutputIndexes,
      });
      setExportPack(response.export_pack);
      setActionMessage(`Export pack đã tạo: ${response.export_pack.output_dir}`);
      await loadResults(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo Export Pack cho job này.');
    } finally {
      setBusyAction(null);
    }
  }

  async function handleOpenPack() {
    if (!jobId) return;
    setBusyAction('open');
    setError(null);
    try {
      if (exportPack?.output_dir) {
        const response = await openFolder(exportPack.output_dir);
        setActionMessage(`Đã mở thư mục: ${response.path}`);
        return;
      }
      const response = await openResultsExportPack(jobId);
      setActionMessage(response.path ? `Đã mở thư mục: ${response.path}` : 'Đã gửi lệnh mở Export Pack.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở thư mục Export Pack.');
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCopyPack() {
    await copyText(exportPack?.output_dir);
    setActionMessage('Đã copy thư mục Export Pack.');
  }

  async function handleRetryFailed() {
    if (!jobId) return;
    setBusyAction('retry');
    setError(null);
    setActionMessage(null);
    try {
      const response = await retryFailedResults(jobId);
      navigate(`/queue/douyin-reup/${response.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể retry failed outputs.');
    } finally {
      setBusyAction(null);
    }
  }

  if (!jobId) {
    return (
      <ResultsLayout title="Kết quả" subtitle="Chưa có job id." actions={<LinkButton to="/douyin-reup" label="Douyin Reup" />}>
        <ResultsEmptyState title="Thiếu job id" message="Mở trang kết quả từ batch đã chạy để xem gallery, Final QA và Export Pack." />
      </ResultsLayout>
    );
  }

  const workflowSteps = [
    { label: 'Nguồn', status: 'done' as const },
    { label: 'Cấu hình', status: 'done' as const },
    { label: 'Xử lý', status: loading || jobRunning ? 'active' as const : 'done' as const },
    { label: 'Đánh giá', status: outputs.length ? 'done' as const : 'pending' as const },
    { label: 'Kết xuất', status: summary.exportEligible ? 'done' as const : 'pending' as const },
    { label: 'Xuất bản', status: exportPack ? 'done' as const : 'pending' as const },
  ];

  return (
    <ResultsLayout
      title="Thư viện kết quả"
      subtitle={`Tác vụ: ${jobId}`}
      statusLabel={jobRunning ? 'Đang cập nhật' : jobStatus ? formatStatus(jobStatus.status) : ''}
      actions={
        <>
          {projectId ? <LinkButton to={`/projects/${projectId}/content`} label="Caption" /> : null}
          {projectId ? <LinkButton to={`/projects/${projectId}/review`} label="Đánh giá" /> : null}
          <LinkButton to="/douyin-reup" label="Batch mới" icon={<Clapperboard size={16} />} />
          <GlassButton variant="secondary" loading={loading} onClick={() => void loadResults()}>
            <RefreshCw size={16} />
            Làm mới
          </GlassButton>
        </>
      }
      summary={
        <>
          <WorkflowStepper steps={workflowSteps} />
          <ResultsSummaryCards summary={summary} jobStatus={jobStatus} />
        </>
      }
      sidePanel={
        <div className="grid gap-5">
          <ResultQAPanel
            batchSummary={douyinSummary?.final_output_qa ?? null}
            busy={busyAction === 'qa'}
            items={items}
            platformTarget={platformTarget}
            onPlatformTargetChange={setPlatformTarget}
            onRunQA={() => void handleRunQA()}
          />
          <ResultRetryPanel failedItems={failedItems} busy={busyAction === 'retry'} onRetryFailed={() => void handleRetryFailed()} />
          <ExportPackPanel
            busy={busyAction === 'export'}
            exportPack={exportPack}
            exportScope={exportScope}
            items={items}
            options={exportOptions}
            outputIndexes={exportOutputIndexes}
            platformTarget={platformTarget}
            selectedCount={selectedCount}
            onCopyPack={() => void handleCopyPack()}
            onCreatePack={() => void handleCreateExportPack()}
            onExportScopeChange={setExportScope}
            onOpenPack={() => void handleOpenPack()}
            onOptionsChange={setExportOptions}
            onPlatformTargetChange={setPlatformTarget}
          />
        </div>
      }
    >
      <div className="grid gap-5">
        <ApiErrorBox error={error} />
        <NotifyOnChange value={actionMessage} variant="success" />
        {actionMessage ? (
          <div className="flex items-start gap-2 rounded-md border border-emerald-300/20 bg-emerald-300/10 px-4 py-3 text-sm text-emerald-100">
            <Sparkles className="mt-0.5 shrink-0" size={16} />
            <span>{actionMessage}</span>
          </div>
        ) : null}

        {loading ? (
          <ResultsSkeleton />
        ) : items.length ? (
          <>
            <ResultsFilterBar
              filter={filter}
              search={search}
              selectedCount={selectedCount}
              selectionMode={selectionMode}
              sort={sort}
              summary={summary}
              totalSelectable={summary.exportEligible}
              viewMode={viewMode}
              onClearSelection={() => setSelectedIds(new Set())}
              onFilterChange={setFilter}
              onSearchChange={setSearch}
              onSelectAll={selectAllEligible}
              onSelectionModeChange={setSelectionMode}
              onSortChange={setSort}
              onViewModeChange={setViewMode}
            />
            <ResultVideoGrid
              items={paginatedItems}
              selectedIds={selectedIds}
              selectionMode={selectionMode}
              viewMode={viewMode}
              onCopyCaption={(item) => void copyCaption(item)}
              onCopyPath={(item) => void copyPath(item)}
              onRevealFile={(item) => void revealResult(item)}
              onPreview={setPreviewItem}
              onShowLog={showLog}
              onToggleSelected={toggleSelected}
            />
            <GlassPagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              className="mt-6"
            />
          </>
        ) : (
          <ResultsEmptyState
            title="Chưa có video đầu ra"
            message="Khi batch hoàn tất, video render, cảnh báo, QA và file export liên quan sẽ xuất hiện tại đây."
            action={<LinkButton to="/douyin-reup" label="Tạo batch mới" />}
          />
        )}
      </div>

      <ResultVideoPreviewModal
        item={previewItem}
        selected={Boolean(previewItem && selectedIds.has(previewItem.id))}
        selectionMode={selectionMode}
        onClose={() => setPreviewItem(null)}
        onCopyCaption={(item) => void copyCaption(item)}
        onCopyPath={(item) => void copyPath(item)}
        onRevealFile={(item) => void revealResult(item)}
        onShowLog={showLog}
        onToggleSelected={toggleSelected}
      />
      <ResultTechnicalLogDrawer
        item={logItem}
        jobStatus={jobStatus}
        open={logOpen}
        onClose={() => {
          setLogOpen(false);
          setLogItem(null);
        }}
      />
    </ResultsLayout>
  );
}

function getExportOutputIndexes(items: NormalizedResultItem[], selectedIds: Set<string>, scope: ExportScope): number[] {
  if (scope === 'selected') {
    return items.filter((item) => item.exportEligible && selectedIds.has(item.id)).map((item) => item.index);
  }
  if (scope === 'qa_passed') {
    return items.filter((item) => item.exportEligible && item.qaStatus === 'passed').map((item) => item.index);
  }
  if (scope === 'include_warnings') {
    return items.filter((item) => item.exportEligible && item.health !== 'failed' && item.health !== 'processing').map((item) => item.index);
  }
  return items.filter((item) => item.exportEligible && item.health === 'ready').map((item) => item.index);
}

function LinkButton({ to, label, icon }: { to: string; label: string; icon?: ReactNode }) {
  return (
    <Link
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white transition hover:border-cyan-300/45 hover:bg-white/12"
      to={to}
    >
      {icon}
      {label}
    </Link>
  );
}

function formatStatus(status: string): string {
  const labels: Record<string, string> = {
    success: 'Thành công',
    warning: 'Có cảnh báo',
    failed: 'Thất bại',
    completed: 'Hoàn thành',
    completed_with_errors: 'Hoàn thành nhưng có lỗi',
    running: 'Đang chạy',
    queued: 'Đang chờ',
    cancelled: 'Đã hủy',
  };
  return labels[status.toLowerCase()] ?? status;
}
