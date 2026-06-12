import { Play, RefreshCw, Route } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { JobStartedView } from '../../types/startWorkflow';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';

export default function StartBatchButton({
  disabled,
  loading,
  label,
  job,
  onStart,
}: {
  disabled: boolean;
  loading: boolean;
  label: string;
  job: JobStartedView | null;
  onStart: () => void;
}) {
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      {job ? (
        <div className="rounded-md border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
          <div className="font-semibold">Batch đã bắt đầu</div>
          <div className="mt-1 break-all text-xs">Job: {job.jobId}</div>
          <div className="mt-1 text-xs">Project: {job.projectName}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/8 px-3 py-2 text-sm font-semibold text-white hover:bg-white/12" to={`/queue/douyin-reup/${job.jobId}`}>
              <Route size={16} />
              Xem tiến trình
            </Link>
            <Link className="inline-flex min-h-10 items-center gap-2 rounded-md border border-cyan-300/50 bg-cyan-300 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-200" to={`/results/${job.jobId}`}>
              Mở kết quả
            </Link>
          </div>
        </div>
      ) : null}
      <GlassButton className="min-h-12 w-full text-base" variant="primary" loading={loading} disabled={disabled} onClick={onStart}>
        {loading ? <RefreshCw size={18} /> : <Play size={18} />}
        {loading ? 'Đang tạo job...' : label}
      </GlassButton>
    </GlassCard>
  );
}
