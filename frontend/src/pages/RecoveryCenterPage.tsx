import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import GlassBadge from '../components/glass/GlassBadge';
import GlassButton from '../components/glass/GlassButton';
import GlassModal from '../components/glass/GlassModal';
import {
  cleanupJobLock,
  getRecoveryCandidates,
  markJobCancelled,
  reconcileJob,
  resumeJob,
  type RecoveryCandidate,
  type ResumeJobRequest,
  type ResumeMode,
} from '../services/jobRecoveryApi';

const defaultResume: ResumeJobRequest = {
  resume_mode: 'reconcile_then_continue',
  skip_completed_outputs: true,
  do_not_overwrite_existing_outputs: true,
  max_items: null,
};

export default function RecoveryCenterPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<RecoveryCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selected, setSelected] = useState<RecoveryCandidate | null>(null);
  const [resumeRequest, setResumeRequest] = useState<ResumeJobRequest>(defaultResume);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  useEffect(() => {
    void refresh();
  }, []);

  const totals = useMemo(() => ({
    recoverable: items.filter((item) => item.recoverable).length,
    completed: items.reduce((sum, item) => sum + item.completed_items, 0),
    failed: items.reduce((sum, item) => sum + item.failed_items, 0),
    interrupted: items.reduce((sum, item) => sum + item.interrupted_items, 0),
  }), [items]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const response = await getRecoveryCandidates();
      setItems(response.data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải Recovery Center.');
    } finally {
      setLoading(false);
    }
  }

  async function runAction(jobId: string, action: () => Promise<unknown>, successMessage: string) {
    setBusyJobId(jobId);
    setError(null);
    setMessage(null);
    try {
      await action();
      setMessage(successMessage);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Thao tác recovery thất bại.');
    } finally {
      setBusyJobId(null);
    }
  }

  async function confirmResume() {
    if (!selected) return;
    await runAction(
      selected.job_id,
      async () => {
        const result = await resumeJob(selected.job_id, resumeRequest);
        if (result.new_job_id) navigate(`/queue/${selected.project_id ?? 'project'}/${result.new_job_id}`);
      },
      'Đã tạo job resume.',
    );
    setSelected(null);
  }

  return (
    <main className="studio-page grid gap-6">
      <section>
        <GlassBadge variant="warning">Khôi phục job</GlassBadge>
        <h1 className="mt-3 text-3xl font-semibold text-white">Recovery Center</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
          Kiểm tra các batch bị gián đoạn, bỏ qua video đã xong và tiếp tục phần còn lại mà không ghi đè output cũ.
        </p>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        <Metric label="Job có thể khôi phục" value={totals.recoverable} />
        <Metric label="Video đã xong" value={totals.completed} />
        <Metric label="Video lỗi" value={totals.failed} />
        <Metric label="Đang dở" value={totals.interrupted} />
      </section>

      <div className="flex flex-wrap gap-2">
        <GlassButton loading={loading} onClick={() => void refresh()}>Refresh</GlassButton>
        <GlassButton variant="ghost" onClick={() => navigate('/results')}>Mở kết quả</GlassButton>
      </div>

      {error ? <Notice tone="error" text={error} /> : null}
      {message ? <Notice tone="success" text={message} /> : null}

      <section className="grid gap-4">
        {items.length ? items.map((item) => (
          <article key={item.job_id} className="glass-card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold text-white">{item.project_name || item.job_id}</h2>
                  <GlassBadge variant={item.recoverable ? 'warning' : 'neutral'}>{statusLabel(item.status)}</GlassBadge>
                </div>
                <div className="mt-1 text-xs text-slate-500">{item.mode} · {item.job_id}</div>
              </div>
              <div className="text-right text-sm text-slate-300">
                <div>{item.completed_items} / {item.total_items} video đã xong</div>
                <div className="text-xs text-slate-500">Checkpoint: {item.last_checkpoint_at || 'Không rõ'}</div>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-cyan-300" style={{ width: `${progress(item)}%` }} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">{item.reason}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <GlassButton variant="primary" disabled={!item.recoverable} onClick={() => { setSelected(item); setResumeRequest(defaultResume); }}>
                Resume safely
              </GlassButton>
              <GlassButton loading={busyJobId === item.job_id} onClick={() => void runAction(item.job_id, () => reconcileJob(item.job_id), 'Đã reconcile output hiện có.')}>
                Reconcile
              </GlassButton>
              <GlassButton variant="ghost" onClick={() => navigate(`/results/${item.project_id ?? 'project'}/${item.job_id}`)}>
                Mở kết quả tạm thời
              </GlassButton>
              <GlassButton variant="ghost" loading={busyJobId === item.job_id} onClick={() => void runAction(item.job_id, () => cleanupJobLock(item.job_id), 'Đã cleanup lock của job.')}>
                Cleanup lock
              </GlassButton>
              <GlassButton variant="danger" loading={busyJobId === item.job_id} onClick={() => void runAction(item.job_id, () => markJobCancelled(item.job_id), 'Đã đánh dấu job là đã hủy.')}>
                Đánh dấu đã hủy
              </GlassButton>
            </div>
          </article>
        )) : (
          <div className="glass-card p-8 text-center text-slate-300">
            Không có job bị gián đoạn. Khi app bị tắt giữa batch, job recoverable sẽ xuất hiện ở đây.
          </div>
        )}
      </section>

      <GlassModal open={Boolean(selected)} title="Tiếp tục xử lý job" onClose={() => setSelected(null)}>
        <div className="grid gap-4 text-sm text-slate-300">
          <div className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-4 leading-6 text-cyan-100">
            Tool sẽ kiểm tra file đã có, bỏ qua video đã render xong và không ghi đè output cũ nếu tùy chọn đang bật.
          </div>
          <label className="grid gap-1.5">
            <span className="font-medium text-slate-200">Resume mode</span>
            <select
              className="h-10 rounded-md border border-white/15 bg-slate-950/90 px-3 text-sm text-white"
              value={resumeRequest.resume_mode}
              onChange={(event) => setResumeRequest({ ...resumeRequest, resume_mode: event.target.value as ResumeMode })}
            >
              <option value="reconcile_then_continue">Reconcile then continue</option>
              <option value="retry_interrupted">Retry interrupted only</option>
              <option value="retry_failed">Retry failed only</option>
              <option value="continue_pending">Continue pending only</option>
            </select>
          </label>
          <Toggle
            label="Bỏ qua video đã xong"
            checked={resumeRequest.skip_completed_outputs}
            onChange={(skip_completed_outputs) => setResumeRequest({ ...resumeRequest, skip_completed_outputs })}
          />
          <Toggle
            label="Không ghi đè output cũ"
            checked={resumeRequest.do_not_overwrite_existing_outputs}
            onChange={(do_not_overwrite_existing_outputs) => setResumeRequest({ ...resumeRequest, do_not_overwrite_existing_outputs })}
          />
          <div className="flex flex-wrap justify-end gap-2">
            <GlassButton variant="ghost" onClick={() => setSelected(null)}>Cancel</GlassButton>
            <GlassButton variant="primary" loading={Boolean(selected && busyJobId === selected.job_id)} onClick={() => void confirmResume()}>
              Resume job
            </GlassButton>
          </div>
        </div>
      </GlassModal>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-card p-4">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-200">
      <input className="h-4 w-4" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function Notice({ tone, text }: { tone: 'error' | 'success'; text: string }) {
  const classes = tone === 'error'
    ? 'border-rose-400/30 bg-rose-400/10 text-rose-100'
    : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100';
  return <div className={`rounded-md border p-3 text-sm ${classes}`}>{text}</div>;
}

function progress(item: RecoveryCandidate): number {
  if (!item.total_items) return 0;
  return Math.max(0, Math.min(100, Math.round((item.completed_items / item.total_items) * 100)));
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    interrupted: 'Bị gián đoạn',
    recoverable: 'Có thể khôi phục',
    failed: 'Lỗi',
    completed_with_warnings: 'Hoàn thành có cảnh báo',
    cancelled: 'Đã hủy',
  };
  return labels[status] ?? status;
}

