import { AlertTriangle, CheckCircle2, Clock3, FileArchive, Gauge, ShieldAlert } from 'lucide-react';
import type { JobStatus } from '../../types/project';
import type { ResultSummary } from '../../utils/resultStatus';
import GlassCard from '../glass/GlassCard';

export default function ResultsSummaryCards({
  summary,
  jobStatus,
}: {
  summary: ResultSummary;
  jobStatus: JobStatus | null;
}) {
  const progress = jobStatus ? `${Math.round(jobStatus.progress)}%` : summary.total ? '100%' : '-';
  const cards = [
    { label: 'Tổng output', value: summary.total, detail: `${summary.exportEligible} có thể export`, icon: FileArchive, tone: 'text-cyan-200' },
    { label: 'Sẵn sàng', value: summary.ready, detail: `${summary.selected} đang chọn`, icon: CheckCircle2, tone: 'text-emerald-300' },
    { label: 'Cảnh báo', value: summary.warnings, detail: `${summary.needsReview} cần review`, icon: AlertTriangle, tone: 'text-amber-300' },
    { label: 'Lỗi', value: summary.failed, detail: `${summary.qaFailed} lỗi QA`, icon: ShieldAlert, tone: 'text-rose-300' },
    { label: 'QA score', value: summary.averageQaScore == null ? '-' : `${summary.averageQaScore}%`, detail: `${summary.qaChecked} đã check`, icon: Gauge, tone: 'text-violet-200' },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <GlassCard className="p-4" key={card.label}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-normal text-slate-400">{card.label}</div>
                <div className="mt-2 text-2xl font-semibold text-white">{card.value}</div>
              </div>
              <Icon className={card.tone} size={22} />
            </div>
            <div className="mt-3 text-xs text-slate-400">{card.detail}</div>
          </GlassCard>
        );
      })}
      <div className="sr-only" aria-live="polite">
        Job progress {progress}
      </div>
      {jobStatus && jobStatus.status !== 'completed' ? (
        <GlassCard className="sm:col-span-2 xl:col-span-5 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="flex min-w-0 items-center gap-2 text-sm text-slate-300">
              <Clock3 className="shrink-0 text-cyan-200" size={16} />
              <span className="truncate">Đang theo dõi job: {jobStatus.current_step || jobStatus.status}</span>
            </div>
            <span className="text-sm font-semibold text-white">{progress}</span>
          </div>
          <div className="h-1 bg-white/8">
            <div className="h-full bg-cyan-300 transition-all" style={{ width: progress }} />
          </div>
        </GlassCard>
      ) : null}
    </div>
  );
}
