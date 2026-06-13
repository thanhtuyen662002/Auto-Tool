import { Activity, ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react';
import { finalOutputQAReportUrl } from '../../api/client';
import type { FinalOutputQABatchSummary, PlatformTarget } from '../../types/project';
import type { NormalizedResultItem } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import GlassBadge from '../glass/GlassBadge';

export default function ResultQAPanel({
  items,
  batchSummary,
  platformTarget,
  onPlatformTargetChange,
  busy,
  onRunQA,
}: {
  items: NormalizedResultItem[];
  batchSummary?: FinalOutputQABatchSummary | null;
  platformTarget: PlatformTarget;
  onPlatformTargetChange: (value: PlatformTarget) => void;
  busy: boolean;
  onRunQA: () => void;
}) {
  const checked = items.filter((item) => item.qaStatus !== 'not_checked');
  const failed = items.filter((item) => item.qaStatus === 'failed');
  const warnings = items.filter((item) => item.qaStatus === 'warning');
  const passed = items.filter((item) => item.qaStatus === 'passed');
  const average = batchSummary?.average_score == null ? null : Math.round((batchSummary.average_score <= 1 ? batchSummary.average_score * 100 : batchSummary.average_score));
  const recentIssues = items.flatMap((item) => (item.qa?.issues ?? []).map((issue) => ({ item, issue }))).slice(0, 4);

  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-white">
            <ShieldCheck size={18} className="text-emerald-300" />
            Đánh giá QA
          </h2>
          <p className="mt-1 text-sm text-slate-400">Kiểm tra kỹ thuật cuối trước khi đóng gói đăng nền tảng.</p>
        </div>
        <GlassBadge variant={failed.length ? 'failed' : warnings.length ? 'warning' : checked.length ? 'success' : 'neutral'}>
          {checked.length ? `Đã kiểm tra ${checked.length}/${items.length}` : 'Chưa kiểm tra'}
        </GlassBadge>
      </div>

      <div className="grid grid-cols-2 gap-2 text-center">
        <Metric label="Đạt (Passed)" value={batchSummary?.passed ?? passed.length} />
        <Metric label="Cảnh báo (Warnings)" value={batchSummary?.passed_with_warnings ?? warnings.length} />
        <Metric label="Lỗi (Failed)" value={batchSummary?.failed ?? failed.length} />
        <Metric label="Trung bình" value={average == null ? '-' : `${average}%`} />
      </div>

      <div className="grid gap-3 border-t border-white/10 pt-4">
        <label>
          <span className="mb-1 block text-xs font-semibold uppercase tracking-normal text-slate-500">Nền tảng đích</span>
          <select
            className="h-10 w-full rounded-md border border-white/15 bg-slate-950/70 px-3 text-sm"
            value={platformTarget}
            onChange={(event) => onPlatformTargetChange(event.target.value as PlatformTarget)}
          >
            <option value="tiktok">TikTok</option>
            <option value="instagram_reels">Instagram Reels</option>
            <option value="youtube_shorts">YouTube Shorts</option>
            <option value="generic_vertical">Video đứng chung</option>
          </select>
        </label>
        <GlassButton variant="primary" loading={busy} disabled={!items.length} onClick={onRunQA}>
          <RefreshCw size={16} />
          Chạy Final QA
        </GlassButton>
      </div>

      <div className="border-t border-white/10 pt-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white">
          <Activity size={16} className="text-cyan-200" />
          Vấn đề mới nhất
        </div>
        {recentIssues.length ? (
          <div className="grid gap-2">
            {recentIssues.map(({ item, issue }, index) => (
              <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs leading-5" key={`${item.id}-${issue.issue_type}-${index}`}>
                <div className={issue.severity === 'critical' ? 'font-semibold text-rose-200' : 'font-semibold text-amber-200'}>
                  {item.filename}: {issue.message}
                </div>
                {issue.suggestion ? <div className="mt-1 text-slate-400">{issue.suggestion}</div> : null}
                {item.qa?.report_path ? (
                  <a className="mt-2 inline-flex items-center gap-1 font-semibold text-cyan-200 hover:text-cyan-100" href={finalOutputQAReportUrl(item.qa.report_path)} target="_blank" rel="noreferrer">
                    <ExternalLink size={13} />
                    Báo cáo QA
                  </a>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm leading-6 text-slate-400">Chưa có issue QA. Chạy Final QA để lấy điểm kỹ thuật thực tế.</p>
        )}
      </div>
    </GlassCard>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/5 p-3">
      <div className="text-lg font-semibold text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{label}</div>
    </div>
  );
}
