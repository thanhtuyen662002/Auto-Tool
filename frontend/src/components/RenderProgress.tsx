import type { JobStatus } from '../types/project';

interface RenderProgressProps {
  job: JobStatus | null;
}

export default function RenderProgress({ job }: RenderProgressProps) {
  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));
  const stalledMinutes = staleMinutes(job);
  return (
    <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-ink">{formatStep(job?.current_step ?? 'queued')}</div>
          <div className="text-xs text-muted">{formatStatus(job?.status ?? 'queued')}</div>
        </div>
        <div className="text-xl font-semibold text-brand">{progress}%</div>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-surface">
        <div className="h-full bg-brand transition-all" style={{ width: `${progress}%` }} />
      </div>
      {stalledMinutes !== null ? (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Không có cập nhật xử lý trong {stalledMinutes} phút. API vẫn có thể trả 200 khi worker nền đã bị kẹt; hãy xem bước hiện tại và nhật ký bên dưới.
        </div>
      ) : null}
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <Metric label="Đã hoàn thành" value={job?.completed_outputs ?? 0} />
        <Metric label="Bị lỗi" value={job?.failed_outputs ?? 0} />
        <Metric label="Tổng số" value={job?.total_outputs ?? 0} />
      </div>
      {job?.cache_summary ? (
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-md bg-emerald-50 p-3 text-emerald-700">
            <div className="text-xs">Cache hit</div>
            <div className="font-semibold">{job.cache_summary.hits ?? 0}</div>
          </div>
          <div className="rounded-md bg-amber-50 p-3 text-amber-800">
            <div className="text-xs">Cache miss</div>
            <div className="font-semibold">{job.cache_summary.misses ?? 0}</div>
          </div>
          <Metric label="Dung lượng cache" value={formatCacheSize(job.cache_summary.cache_size_mb ?? 0)} />
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

function formatCacheSize(sizeMb: number): string {
  if (sizeMb >= 1024) return `${(sizeMb / 1024).toFixed(2)} GB`;
  return `${sizeMb.toFixed(1)} MB`;
}

function formatStatus(status: string): string {
  const normalized = status.toLowerCase();
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    running: 'Đang chạy',
    pausing: 'Đang yêu cầu tạm dừng',
    paused: 'Đã tạm dừng',
    resuming: 'Đang tiếp tục',
    cancel_requested: 'Đang yêu cầu hủy',
    cancelled: 'Đã hủy',
    completed: 'Hoàn thành',
    completed_with_errors: 'Hoàn thành nhưng có lỗi',
    completed_with_warnings: 'Hoàn thành có cảnh báo',
    failed: 'Thất bại',
  };
  return labels[normalized] ?? status;
}

function formatStep(step: string): string {
  const normalized = step.toLowerCase();
  const detailedLabels: Record<string, string> = {
    subtitle_source: 'Đang xác định nguồn phụ đề',
    asr_extracting_audio: 'Đang tách âm thanh cho nhận diện thoại',
    asr_loading_model: 'Đang nạp model nhận diện thoại',
    asr_transcribing: 'Đang nhận diện lời thoại',
    asr_writing_subtitles: 'Đang ghi phụ đề nhận diện',
    ocr_probe: 'Đang kiểm tra chữ trên video',
    ocr_loading_model: 'Đang chuẩn bị bộ đọc chữ',
    ocr_sampling_frames: 'Đang lấy frame phụ đề',
    ocr_recognizing: 'Đang nhận diện chữ trên video',
    ocr_merging_lines: 'Đang ghép các dòng chữ nhận diện',
    translation: 'Đang dịch phụ đề',
    timing_guard: 'Đang căn thời gian phụ đề',
    ffmpeg_render: 'Đang xuất video cuối',
    final_output_qa: 'Đang kiểm tra video đầu ra',
  };
  const detailedStep = Object.keys(detailedLabels).find((key) => normalized === key || normalized.endsWith(`_${key}`));
  if (detailedStep) return detailedLabels[detailedStep];
  const labels: Record<string, string> = {
    queued: 'Đang chờ',
    starting: 'Đang bắt đầu',
    scanning_media: 'Đang quét video nguồn',
    creating_segments: 'Đang tạo cảnh cắt',
    scoring_segments: 'Đang chấm điểm cảnh',
    building_timelines: 'Đang dựng dòng thời gian',
    paused: 'Đã tạm dừng',
    cancelled: 'Đã hủy',
    completed: 'Hoàn thành',
    failed: 'Thất bại',
  };
  if (normalized.startsWith('rendering_video_')) return `Đang render video ${normalized.replace('rendering_video_', '')}`;
  if (normalized.startsWith('douyin_video_')) return `Đang xử lý Douyin video ${normalized.replace('douyin_video_', '').replace('_done', '')}`;
  if (normalized.startsWith('retry_')) return `Retry: ${formatStep(normalized.replace('retry_', ''))}`;
  return labels[normalized] ?? step;
}

function staleMinutes(job: JobStatus | null): number | null {
  if (!job || job.status !== 'running' || !job.updated_at) return null;
  const updatedAt = new Date(job.updated_at).getTime();
  if (!Number.isFinite(updatedAt)) return null;
  const minutes = Math.floor((Date.now() - updatedAt) / 60_000);
  return minutes >= 5 ? minutes : null;
}
