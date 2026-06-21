import { useEffect, useState, useMemo } from 'react';
import { Clapperboard, FolderOpen, Loader2, Clock, ExternalLink, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { listJobs, deleteJob } from '../api/client';
import type { JobStatus } from '../types/project';
import ResultsLayout from '../components/results/ResultsLayout';
import GlassBadge from '../components/glass/GlassBadge';
import GlassButton from '../components/glass/GlassButton';
import GlassPagination from '../components/glass/GlassPagination';
import GlassModal from '../components/glass/GlassModal';
import NotifyOnChange from '../components/notifications/NotifyOnChange';


const ACTIVE_STATUSES = new Set(['queued', 'running', 'paused']);

export default function ResultsPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const pageSize = 10;

  const [jobToDelete, setJobToDelete] = useState<JobStatus | null>(null);
  const [deletingJob, setDeletingJob] = useState(false);

  async function handleDeleteJob() {
    if (!jobToDelete) return;
    setDeletingJob(true);
    setError(null);
    setMessage(null);
    try {
      const response = await deleteJob(jobToDelete.job_id);
      if (response.success) {
        setJobToDelete(null);
        setMessage('Đã xóa tác vụ.');
        await load(false, currentPage);
      } else {
        setError('Không thể xóa tác vụ.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Có lỗi xảy ra khi xóa tác vụ.');
    } finally {
      setDeletingJob(false);
    }
  }


  async function load(quiet = false, page = currentPage) {
    if (!quiet) setLoading(true);
    try {
      const offset = (page - 1) * pageSize;
      const response = await listJobs(pageSize, offset);
      if (response.success) {
        setJobs(response.jobs);
        setTotalPages(Math.ceil((response.total || 0) / pageSize));
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải danh sách tác vụ.');
    } finally {
      if (!quiet) setLoading(false);
    }
  }

  useEffect(() => {
    void load(false, currentPage);
  }, [currentPage]);


  // Polling for active jobs
  const hasActiveJob = useMemo(() => jobs.some((job) => ACTIVE_STATUSES.has(job.status)), [jobs]);

  useEffect(() => {
    if (!hasActiveJob) return undefined;
    const timer = window.setInterval(() => {
      void load(true, currentPage);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, currentPage]);

  function getJobTypeLabel(projectId: string): string {
    if (projectId.startsWith('douyin_reup_')) return 'Reup có thoại (Douyin)';
    if (projectId.startsWith('silent_')) return 'Reup không thoại';
    if (projectId.startsWith('subtitle_review_')) return 'Sửa phụ đề';
    return 'Video Affiliate';
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case 'queued':
        return <GlassBadge variant="neutral">Chờ chạy</GlassBadge>;
      case 'running':
        return <GlassBadge variant="processing"><Loader2 className="mr-1 h-3 w-3 animate-spin inline" />Đang chạy</GlassBadge>;
      case 'paused':
        return <GlassBadge variant="warning">Tạm dừng</GlassBadge>;
      case 'completed':
        return <GlassBadge variant="success">Hoàn thành</GlassBadge>;
      case 'completed_with_errors':
        return <GlassBadge variant="warning">Hoàn thành có lỗi</GlassBadge>;
      case 'failed':
        return <GlassBadge variant="failed">Lỗi</GlassBadge>;
      case 'cancelled':
        return <GlassBadge variant="neutral">Đã hủy</GlassBadge>;
      default:
        return <GlassBadge variant="neutral">{status}</GlassBadge>;
    }
  }

  return (
    <ResultsLayout
      title="Tác vụ & Kết quả"
      subtitle="Theo dõi các tiến trình render thời gian thực, quản lý hàng đợi và xem kết quả video đầu ra."
      actions={
        <>
          <LinkButton to="/douyin-reup" label="Reup có thoại" icon={<Clapperboard size={16} />} />
          <LinkButton to="/silent-mode" label="Reup không thoại" icon={<FolderOpen size={16} />} />
        </>
      }
    >
      <div className="space-y-4">
        <NotifyOnChange value={error} variant="error" />
        <NotifyOnChange value={message} variant="success" />
        {error ? (
          <div className="rounded-md border border-rose-400/30 bg-rose-400/10 p-4 text-sm text-rose-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="flex min-h-[300px] items-center justify-center rounded-lg border border-white/10 bg-[#0c101f]/40">
            <div className="text-center">
              <Loader2 className="mx-auto h-8 w-8 animate-spin text-cyan-300" />
              <p className="mt-3 text-sm text-slate-400">Đang tải danh sách tác vụ...</p>
            </div>
          </div>
        ) : jobs.length ? (
          <>
            <div className="grid gap-4">
              {jobs.map((job) => {
                const isActive = ACTIVE_STATUSES.has(job.status);
                const formattedDate = new Date(job.created_at || Date.now()).toLocaleString('vi-VN');
                const progressVal = job.progress ?? 0;
                const linkUrl = isActive
                  ? `/queue/${job.project_id || 'project'}/${job.job_id}`
                  : `/results/${job.project_id || 'project'}/${job.job_id}`;

                return (
                  <div key={job.job_id} className="glass-card p-5 border border-white/10 bg-[#0e1628]/40 hover:border-cyan-300/30 transition-all duration-300 hover:scale-[1.005]">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-lg font-semibold text-white truncate max-w-md">
                            {job.project_name || `Dự án: ${job.project_id}`}
                          </h2>
                          {getStatusBadge(job.status)}
                          <span className="text-[11px] rounded bg-white/5 px-2 py-0.5 font-medium text-slate-400">
                            {getJobTypeLabel(job.project_id || '')}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-400">
                          <span className="flex items-center gap-1">
                            <Clock size={13} />
                            {formattedDate}
                          </span>
                          <span className="font-mono text-slate-500">ID: {job.job_id}</span>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1 text-right">
                        <div className="text-sm font-semibold text-white">
                          {job.completed_outputs} / {job.total_outputs} video đã xong
                        </div>
                        {job.failed_outputs > 0 && (
                          <div className="text-xs text-rose-300 font-medium">
                            {job.failed_outputs} video bị lỗi
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                      <div className="flex-1 min-w-[200px]">
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>{job.current_step || 'Đang chuẩn bị...'}</span>
                          <span className="font-semibold text-cyan-200">{progressVal}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-white/10">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              job.status === 'failed'
                                ? 'bg-rose-500'
                                : job.status === 'completed'
                                ? 'bg-emerald-400'
                                : 'bg-cyan-300'
                            }`}
                            style={{ width: `${progressVal}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Link to={linkUrl}>
                          <GlassButton
                            variant={isActive ? 'primary' : 'secondary'}
                            className="min-h-9 px-4 text-xs hover:scale-[1.03] active:scale-[0.97] transition-all"
                          >
                            {isActive ? 'Giám sát hàng đợi' : 'Xem kết quả'}
                            <ExternalLink size={12} className="ml-1" />
                          </GlassButton>
                        </Link>
                        <GlassButton
                          variant="danger"
                          className="min-h-9 px-3 text-xs hover:scale-[1.03] active:scale-[0.97] transition-all"
                          onClick={() => setJobToDelete(job)}
                          title="Xóa tác vụ"
                          aria-label="Xóa tác vụ"
                        >
                          <Trash2 size={14} />
                        </GlassButton>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <GlassPagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              className="mt-6"
            />
          </>
        ) : (
          <div className="glass-card p-12 text-center border border-white/10 bg-[#0e1628]/20">
            <Clock className="mx-auto h-12 w-12 text-slate-500" />
            <h3 className="mt-4 text-lg font-semibold text-white">Chưa có tác vụ nào</h3>
            <p className="mt-2 text-sm text-slate-400 max-w-md mx-auto">
              Khi bạn khởi chạy render video có thoại, video không thoại hoặc video affiliate, các tiến trình và hàng đợi render sẽ được hiển thị và theo dõi tại đây.
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <Link to="/douyin-reup">
                <GlassButton variant="primary" className="text-xs">Bắt đầu ngay</GlassButton>
              </Link>
            </div>
          </div>
        )}
      </div>

      <GlassModal
        open={jobToDelete !== null}
        title="Xác nhận xóa tác vụ"
        onClose={() => setJobToDelete(null)}
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-200">
            Bạn có chắc chắn muốn xóa tác vụ của dự án <strong>{jobToDelete?.project_name || jobToDelete?.project_id}</strong>?
          </p>
          <p className="text-xs text-rose-300">
            Hành động này sẽ xóa vĩnh viễn tiến trình chạy, nhật ký logs và các kết quả tạm thời của tác vụ này khỏi hệ thống.
          </p>
          {jobToDelete && ACTIVE_STATUSES.has(jobToDelete.status) && (
            <p className="text-xs text-amber-300 font-medium">
              Cảnh báo: Tác vụ này đang ở trạng thái hoạt động ({jobToDelete.status === 'running' ? 'đang chạy' : jobToDelete.status === 'paused' ? 'tạm dừng' : 'chờ chạy'}). Việc xóa tác vụ sẽ làm gián đoạn tiến trình hiện tại.
            </p>
          )}
          <div className="flex justify-end gap-3 mt-6">
            <GlassButton variant="ghost" onClick={() => setJobToDelete(null)}>
              Hủy bỏ
            </GlassButton>
            <GlassButton variant="danger" loading={deletingJob} onClick={() => void handleDeleteJob()}>
              Xác nhận xóa
            </GlassButton>
          </div>
        </div>
      </GlassModal>
    </ResultsLayout>
  );
}

function LinkButton({ to, label, icon }: { to: string; label: string; icon: ReactNode }) {
  return (
    <Link
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white transition hover:border-cyan-300/45 hover:bg-white/12 hover:scale-[1.02] active:scale-[0.98]"
      to={to}
    >
      {icon}
      {label}
    </Link>
  );
}
