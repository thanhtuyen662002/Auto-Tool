import { CheckCircle2, Clock3, ListChecks, Route } from 'lucide-react';
import type { JobStatus } from '../../types/project';
import type { StartPresetViewModel, StartScanSummary, StartWorkflowMode } from '../../types/startWorkflow';
import GlassBadge from '../glass/GlassBadge';
import GlassCard from '../glass/GlassCard';
import JobProgressPanel from '../jobs/JobProgressPanel';

export default function WorkflowPreviewPanel({
  mode,
  preset,
  scanSummary,
  jobStatus,
}: {
  mode: StartWorkflowMode;
  preset?: StartPresetViewModel;
  scanSummary: StartScanSummary | null;
  jobStatus: JobStatus | null;
}) {
  const steps = workflowSteps(mode, preset);
  return (
    <GlassCard className="grid gap-4 p-5" strong>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-white">
            <Route size={18} className="text-cyan-200" />
            Xem trước quy trình
          </h2>
          <p className="mt-1 text-sm text-slate-400">{preset ? preset.name : 'Chưa chọn preset'}</p>
        </div>
        {preset ? <GlassBadge variant={preset.autoRender ? 'warning' : 'success'}>{preset.reviewRequired ? 'Có duyệt' : 'Render ngay'}</GlassBadge> : null}
      </div>
      <div className="grid gap-2">
        {steps.map((step, index) => (
          <div className="flex gap-3 rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-200" key={step}>
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cyan-300/15 text-xs font-semibold text-cyan-100">{index + 1}</span>
            <span>{step}</span>
          </div>
        ))}
      </div>
      <div className="grid gap-2 border-t border-white/10 pt-4 text-sm">
        <InfoLine label="Duyệt trước" value={preset?.reviewRequired ? 'Bắt buộc' : 'Bỏ qua'} />
        <InfoLine label="Render tự động" value={preset?.autoRender ? 'Có' : 'Không'} />
        <InfoLine
          label="Nguồn caption"
          value={mode === 'silent_immersive' ? 'OCR nếu có chữ, nếu không dùng template theo ngành.' : 'Tự chọn subtitle có sẵn, giọng nói hoặc chữ trên màn hình.'}
        />
      </div>
      {scanSummary ? (
        <div className="rounded-md border border-white/10 bg-white/5 p-3 text-sm text-slate-300">
          <div className="flex items-center gap-2 font-semibold text-white">
            <ListChecks size={16} className="text-emerald-300" />
            Đã scan {scanSummary.valid} video
          </div>
          <div className="mt-1 text-xs text-slate-400">{scanSummary.vertical} dọc, {scanSummary.square} vuông, {scanSummary.horizontal} ngang</div>
        </div>
      ) : null}
      {jobStatus ? (
        <div className="grid gap-3 border-t border-white/10 pt-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            {['completed', 'completed_with_errors', 'failed'].includes(jobStatus.status) ? <CheckCircle2 size={16} className="text-emerald-300" /> : <Clock3 size={16} className="text-cyan-200" />}
            {jobStatus.status === 'queued' ? 'Batch đã bắt đầu' : jobStatus.status}
          </div>
          <JobProgressPanel progress={jobStatus.progress} currentStep={jobStatus.current_step} completed={jobStatus.completed_outputs} total={jobStatus.total_outputs} failed={jobStatus.failed_outputs} warnings={jobStatus.logs.filter((log) => log.level.toLowerCase() === 'warning').length} />
        </div>
      ) : null}
    </GlassCard>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="text-right font-semibold text-slate-200">{value}</span>
    </div>
  );
}

function workflowSteps(mode: StartWorkflowMode, preset?: StartPresetViewModel): string[] {
  if (mode === 'silent_immersive') {
    return ['Nhận diện video không thoại', 'Chia cảnh', 'Tạo caption tiếng Việt', preset?.reviewRequired ? 'Duyệt caption' : 'Render MP4', 'Kiểm tra video cuối', 'Gói xuất bản'];
  }
  if (preset?.autoRender) return ['Scan video', 'Nhận diện giọng nói/chữ', 'Dịch phụ đề', 'Render MP4', 'Kiểm tra video cuối', 'Gói xuất bản'];
  return ['Scan video', 'Nhận diện giọng nói/chữ', 'Dịch phụ đề', 'Mở màn duyệt phụ đề', 'Render MP4', 'Gói xuất bản'];
}
