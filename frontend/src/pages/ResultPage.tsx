import { Clapperboard, RefreshCw, Share2, SlidersHorizontal, Sparkles } from 'lucide-react';
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
  const [isDouyinReup, setIsDouyinReup] = useState(false);
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

  // Fleet Queue state
  const [showFleetModal, setShowFleetModal] = useState(false);
  const [fleetChannels, setFleetChannels] = useState<{ id: string; channel_name: string; platform: string }[]>([]);
  const [fleetSelectedChannels, setFleetSelectedChannels] = useState<string[]>([]);
  const [fleetLoading, setFleetLoading] = useState(false);
  const [fleetChannelsLoading, setFleetChannelsLoading] = useState(false);

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
        setIsDouyinReup(view.isDouyinReup);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Không thể tải kết quả tác vụ.');
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
  const pageStart = visibleItems.length ? (currentPage - 1) * pageSize + 1 : 0;
  const pageEnd = Math.min(currentPage * pageSize, visibleItems.length);
  const paginatedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return visibleItems.slice(start, start + pageSize);
  }, [visibleItems, currentPage, pageSize]);
  const selectedItems = useMemo(() => items.filter((item) => selectedIds.has(item.id)), [items, selectedIds]);
  const selectedCount = selectedItems.length;
  const selectedExportCount = useMemo(() => selectedItems.filter((item) => item.exportEligible).length, [selectedItems]);
  const summary = useMemo(() => summarizeResults(items, selectedCount), [items, selectedCount]);
  const failedItems = useMemo(() => items.filter((item) => item.health === 'failed' || item.qaStatus === 'failed'), [items]);
  const isDouyinResult = isDouyinReup || Boolean(douyinSummary || (jobStatus?.project_id || projectId || '').toLowerCase().includes('douyin'));
  const canSelectItem = useMemo(
    () => (item: NormalizedResultItem) => (isDouyinResult ? Boolean(item.sourceVideo) : item.exportEligible),
    [isDouyinResult],
  );
  const totalSelectable = useMemo(() => items.filter(canSelectItem).length, [canSelectItem, items]);
  const selectedRetryVideoIds = useMemo(
    () => selectedItems.filter((item) => Boolean(item.sourceVideo)).map((item) => `video_${String(item.index).padStart(3, '0')}`),
    [selectedItems],
  );
  const reupAdjustUrl = useMemo(() => {
    if (!jobId) return '/douyin-reup';
    const params = new URLSearchParams({ job_id: jobId, resume: '1' });
    if (selectedRetryVideoIds.length) params.set('video_ids', selectedRetryVideoIds.join(','));
    return `/douyin-reup?${params.toString()}`;
  }, [jobId, selectedRetryVideoIds]);
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

  useEffect(() => {
    if (totalPages > 0 && currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  function toggleSelected(item: NormalizedResultItem) {
    if (!canSelectItem(item)) return;
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(item.id)) next.delete(item.id);
      else next.add(item.id);
      return next;
    });
  }

  function selectAllEligible() {
    setSelectedIds(new Set(items.filter(canSelectItem).map((item) => item.id)));
  }

  async function copyPath(item: NormalizedResultItem) {
    await copyText(item.path);
    setActionMessage(`Đã copy path: ${item.filename}`);
  }

  async function copyCaption(item: NormalizedResultItem) {
    await copyText(captionBundle(item));
    setActionMessage(`Đã sao chép lời bình: ${item.filename}`);
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

  async function loadCompleteJobLog() {
    if (!jobId) return;
    const currentTotal = jobStatus?.logs_total ?? 0;
    const currentCount = jobStatus?.logs?.length ?? 0;
    if (currentTotal > 0 && currentCount >= currentTotal && !jobStatus?.logs_truncated) return;
    try {
      const view = await fetchResultsView(jobId, { jobLogLimit: 0 });
      setOutputs(view.outputs);
      setJobStatus(view.jobStatus);
      setDouyinSummary(view.douyinSummary);
      setExportPack(view.exportPack);
      setIsDouyinReup(view.isDouyinReup);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải đầy đủ nhật ký tác vụ.');
    }
  }

  function showLog(item: NormalizedResultItem) {
    setLogItem(item);
    setLogOpen(true);
    void loadCompleteJobLog();
  }

  async function handleRunQA() {
    if (!jobId) return;
    setBusyAction('qa');
    setError(null);
    setActionMessage(null);
    try {
      const response = await runFinalQA(jobId, platformTarget);
      await loadResults(true);
      setActionMessage(`Đã kiểm tra chất lượng ${response.summary.total_checked} video.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể kiểm tra chất lượng cho tác vụ này.');
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
      setActionMessage(`Đã tạo gói xuất bản: ${response.export_pack.output_dir}`);
      await loadResults(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo gói xuất bản cho tác vụ này.');
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
      setActionMessage(response.path ? `Đã mở thư mục: ${response.path}` : 'Đã gửi lệnh mở gói xuất bản.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể mở thư mục gói xuất bản.');
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCopyPack() {
    await copyText(exportPack?.output_dir);
    setActionMessage('Đã sao chép thư mục gói xuất bản.');
  }

  async function openFleetModal() {
    setShowFleetModal(true);
    setFleetChannelsLoading(true);
    try {
      const res = await fetch('/api/fleet/channels');
      const data = await res.json();
      setFleetChannels(Array.isArray(data) ? data : []);
      // Pre-select all channels
      setFleetSelectedChannels(Array.isArray(data) ? data.map((c: any) => c.id) : []);
    } catch {
      setFleetChannels([]);
    } finally {
      setFleetChannelsLoading(false);
    }
  }

  async function handleAddToFleet() {
    if (!fleetSelectedChannels.length) return;
    setFleetLoading(true);
    try {
      const eligibleSelected = selectedItems.filter((item) => item.exportEligible);
      const payload = {
        items: eligibleSelected.map((item) => ({
          video_path: item.path,
          title: item.filename.replace(/\.[^.]+$/, ''),
          caption: item.caption || null,
          hashtags: item.hashtags.join(' ') || null,
        })),
        channel_ids: fleetSelectedChannels,
      };
      const res = await fetch('/api/fleet/queue/add-from-results', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi đưa vào Fleet.');
      setActionMessage(data.message || `Đã lên lịch ${eligibleSelected.length} video thành công.`);
      setShowFleetModal(false);
      setSelectedIds(new Set());
    } catch (err: any) {
      setError(err.message || 'Không thể đưa video vào lịch đăng.');
      setShowFleetModal(false);
    } finally {
      setFleetLoading(false);
    }
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
      setError(err instanceof Error ? err.message : 'Không thể chạy lại các video lỗi.');
    } finally {
      setBusyAction(null);
    }
  }

  if (!jobId) {
    return (
      <ResultsLayout title="Kết quả" subtitle="Chưa có mã tác vụ." actions={<LinkButton to="/douyin-reup" label="Douyin Reup" />}>
        <ResultsEmptyState title="Thiếu mã tác vụ" message="Mở trang kết quả từ lô đã chạy để xem video, kiểm tra chất lượng và gói xuất bản." />
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
          {isDouyinResult ? <LinkButton to={reupAdjustUrl} label="Chỉnh/render lại" icon={<SlidersHorizontal size={16} />} /> : null}
          {projectId && !isDouyinResult ? <LinkButton to={`/projects/${projectId}/content`} label="Lời bình" /> : null}
          {projectId && !isDouyinResult ? <LinkButton to={`/projects/${projectId}/review`} label="Đánh giá" /> : null}
          {selectedExportCount > 0 ? (
            <GlassButton
              variant="primary"
              loading={fleetLoading}
              onClick={() => void openFleetModal()}
            >
              <Share2 size={16} className="mr-1 text-slate-950" />
              Đưa vào Fleet ({selectedExportCount} video)
            </GlassButton>
          ) : null}
          <LinkButton to="/douyin-reup" label="Lô mới" icon={<Clapperboard size={16} />} />
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
          {isDouyinResult ? (
            <ResultReupAdjustPanel
              selectedCount={selectedRetryVideoIds.length}
              targetUrl={reupAdjustUrl}
              onEnableSelection={() => setSelectionMode(true)}
            />
          ) : null}
          <ResultRetryPanel failedItems={failedItems} busy={busyAction === 'retry'} onRetryFailed={() => void handleRetryFailed()} />
          <ExportPackPanel
            busy={busyAction === 'export'}
            exportPack={exportPack}
            exportScope={exportScope}
            items={items}
            options={exportOptions}
            outputIndexes={exportOutputIndexes}
            platformTarget={platformTarget}
            selectedCount={selectedExportCount}
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
              totalSelectable={totalSelectable}
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
              selectionLabel={isDouyinResult ? 'Chọn sửa lại' : 'Chọn xuất'}
              viewMode={viewMode}
              canSelectItem={canSelectItem}
              onCopyCaption={(item) => void copyCaption(item)}
              onCopyPath={(item) => void copyPath(item)}
              onRevealFile={(item) => void revealResult(item)}
              onPreview={setPreviewItem}
              onShowLog={showLog}
              onToggleSelected={toggleSelected}
            />
            {visibleItems.length ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-400">
                <span>
                  Đang xem <span className="font-semibold text-white">{pageStart}-{pageEnd}</span> / {visibleItems.length} video
                </span>
                <GlassPagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={setCurrentPage}
                  className="mt-0"
                />
              </div>
            ) : null}
          </>
        ) : (
          <ResultsEmptyState
            title="Chưa có video đầu ra"
            message="Khi lô hoàn tất, video đã dựng, cảnh báo, điểm kiểm tra và tệp xuất bản liên quan sẽ xuất hiện tại đây."
            action={<LinkButton to="/douyin-reup" label="Tạo batch mới" />}
          />
        )}
      </div>

      <ResultVideoPreviewModal
        item={previewItem}
        items={visibleItems}
        selected={Boolean(previewItem && selectedIds.has(previewItem.id))}
        selectionMode={selectionMode}
        selectionLabel={isDouyinResult ? 'Chọn sửa lại' : 'Chọn xuất'}
        canSelectItem={canSelectItem}
        onClose={() => setPreviewItem(null)}
        onCopyCaption={(item) => void copyCaption(item)}
        onCopyPath={(item) => void copyPath(item)}
        onRevealFile={(item) => void revealResult(item)}
        onShowLog={showLog}
        onToggleSelected={toggleSelected}
        onNavigate={setPreviewItem}
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

      {/* Fleet Queue Modal */}
      {showFleetModal && (
        <FleetQueueModal
          channels={fleetChannels}
          selectedChannels={fleetSelectedChannels}
          videoCount={selectedExportCount}
          loading={fleetLoading}
          channelsLoading={fleetChannelsLoading}
          onToggleChannel={(id) =>
            setFleetSelectedChannels((prev) =>
              prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
            )
          }
          onConfirm={() => void handleAddToFleet()}
          onClose={() => setShowFleetModal(false)}
        />
      )}
    </ResultsLayout>
  );
}

function ResultReupAdjustPanel({
  selectedCount,
  targetUrl,
  onEnableSelection,
}: {
  selectedCount: number;
  targetUrl: string;
  onEnableSelection: () => void;
}) {
  return (
    <div className="glass-card-strong grid gap-4 p-5">
      <div className="flex items-start gap-3">
        <SlidersHorizontal className="mt-0.5 shrink-0 text-cyan-200" size={20} />
        <div className="min-w-0">
          <h2 className="font-semibold text-white">Chỉnh vị trí sub / render lại</h2>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            Nếu video bị sai vị trí sub hoặc nền che sub Trung, hãy chọn video ở danh sách rồi mở lại màn Reup Douyin để chỉnh cài đặt.
          </p>
        </div>
      </div>
      <div className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm leading-6 text-cyan-50">
        {selectedCount > 0
          ? `Đã chọn ${selectedCount} video. Khi mở màn chỉnh, các video này sẽ được tick sẵn để render lại.`
          : 'Chưa chọn video nào. Bạn vẫn có thể mở màn chỉnh, hoặc bấm Chọn video trước để render lại đúng video lỗi.'}
      </div>
      <div className="grid gap-2">
        <button
          className="min-h-10 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white transition hover:border-cyan-300/45 hover:bg-white/12"
          type="button"
          onClick={onEnableSelection}
        >
          Chọn video cần render lại
        </button>
        <Link
          className="inline-flex min-h-10 items-center justify-center rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
          to={targetUrl}
        >
          {selectedCount > 0 ? `Chỉnh cài đặt cho ${selectedCount} video đã chọn` : 'Mở cài đặt để chỉnh'}
        </Link>
      </div>
    </div>
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

function FleetQueueModal({
  channels,
  selectedChannels,
  videoCount,
  loading,
  channelsLoading,
  onToggleChannel,
  onConfirm,
  onClose,
}: {
  channels: { id: string; channel_name: string; platform: string }[];
  selectedChannels: string[];
  videoCount: number;
  loading: boolean;
  channelsLoading: boolean;
  onToggleChannel: (id: string) => void;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const platformIcon = (platform: string) => {
    if (platform === 'youtube') return '📺';
    if (platform === 'tiktok') return '🎵';
    return '🌐';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        role="presentation"
      />

      {/* Modal */}
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl shadow-black/50 backdrop-blur-md">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400/10 border border-cyan-400/20">
              <Share2 className="text-cyan-400" size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-white text-sm">Đưa vào lịch đăng Fleet</h2>
              <p className="text-xs text-slate-400">{videoCount} video được chọn</p>
            </div>
          </div>
          <button
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white transition-colors"
            onClick={onClose}
            type="button"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4">
          <p className="text-sm text-slate-300 mb-4">
            Chọn kênh để đưa <strong className="text-white">{videoCount} video</strong> vào hàng đợi đăng bài. 
            Hệ thống sẽ tự động phân bố theo khung giờ đã cấu hình.
          </p>

          {channelsLoading ? (
            <div className="flex items-center justify-center py-8 text-slate-400 text-sm gap-2">
              <div className="h-4 w-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              Đang tải danh sách kênh...
            </div>
          ) : channels.length === 0 ? (
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-200">
              ⚠️ Chưa có kênh nào được liên kết. Vui lòng vào tab Fleet → Kênh liên kết để thêm kênh trước.
            </div>
          ) : (
            <div className="grid gap-2 max-h-52 overflow-y-auto pr-1">
              {channels.map((ch) => {
                const checked = selectedChannels.includes(ch.id);
                return (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => onToggleChannel(ch.id)}
                    className={`flex items-center gap-3 w-full rounded-lg border px-3 py-2.5 text-left transition-all ${
                      checked
                        ? 'border-cyan-400/40 bg-cyan-400/10 text-white'
                        : 'border-white/10 bg-white/3 text-slate-300 hover:border-white/20 hover:bg-white/8'
                    }`}
                  >
                    <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors ${
                      checked ? 'border-cyan-400 bg-cyan-400' : 'border-slate-600 bg-transparent'
                    }`}>
                      {checked && <span className="text-slate-950 text-xs font-bold">✓</span>}
                    </div>
                    <span className="text-base">{platformIcon(ch.platform)}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{ch.channel_name}</p>
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider">{ch.platform}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-white/10 px-6 py-4">
          <button
            type="button"
            className="rounded-lg border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
            onClick={onClose}
          >
            Huỷ
          </button>
          <button
            type="button"
            disabled={loading || selectedChannels.length === 0 || channels.length === 0}
            onClick={onConfirm}
            className="flex items-center gap-2 rounded-lg bg-cyan-400 px-5 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="h-4 w-4 rounded-full border-2 border-slate-950 border-t-transparent animate-spin" />
            ) : (
              <Share2 size={14} />
            )}
            {loading ? 'Đang lập lịch...' : `Lập lịch cho ${selectedChannels.length} kênh`}
          </button>
        </div>
      </div>
    </div>
  );
}
