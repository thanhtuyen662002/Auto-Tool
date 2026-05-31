import type { JobOutput } from '../types/project';
import WarningBox from './WarningBox';

interface ResultListProps {
  outputs: JobOutput[];
}

function copy(value?: string | null) {
  if (value) void navigator.clipboard.writeText(value);
}

export default function ResultList({ outputs }: ResultListProps) {
  if (!outputs.length) {
    return <div className="rounded-md border border-line bg-white p-5 text-sm text-muted">Chưa có video đầu ra.</div>;
  }

  return (
    <div className="space-y-4">
      {outputs.map((output) => {
        const errorText = shortText(output.error || output.errors?.[0] || '');
        const warnings = output.warnings ?? [];
        const captionText = captionWithHashtags(output);
        return (
          <article key={output.index} className="rounded-lg border border-line bg-white p-5 shadow-panel">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h2 className="text-lg font-semibold text-ink">Video {String(output.index).padStart(3, '0')}</h2>
                  <StatusBadge status={output.status} warnings={warnings.length} />
                </div>
                {errorText ? <p className="mt-1 max-w-3xl text-sm text-red-700">{errorText}</p> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {errorText ? (
                  <button
                    className="rounded-md border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:border-red-400"
                    type="button"
                    onClick={() => copy(output.errors?.join('\n') || output.error)}
                  >
                    Sao chép lỗi
                  </button>
                ) : null}
                <button
                  className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                  type="button"
                  onClick={() => copy(output.path)}
                >
                  Sao chép đường dẫn video
                </button>
                {captionText ? (
                  <button
                    className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
                    type="button"
                    onClick={() => copy(captionText)}
                  >
                    Sao chép mô tả và hashtag
                  </button>
                ) : null}
                <button
                  className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand"
                  type="button"
                  disabled={!output.log_file}
                  onClick={() => openLocalPath(output.log_file)}
                >
                  Mở nhật ký
                </button>
              </div>
            </div>

            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <InfoRow label="Trạng thái" value={formatStatus(output.status)} />
              <InfoRow label="Thời lượng" value={output.duration ? `${output.duration.toFixed(1)}s` : '-'} />
              <InfoRow label="Dòng thời gian" value={formatId(output.timeline_template)} />
              <InfoRow label="Kiểu kịch bản" value={formatId(output.script_variant_id)} />
              <InfoRow label="Tạo giọng đọc" value={formatId(output.tts_provider)} />
              <InfoRow label="Cảnh báo" value={String(warnings.length)} />
            </dl>

            <WarningBox warnings={warnings} />

            <dl className="mt-4 grid gap-3 text-sm">
              <PathRow label="Đường dẫn" value={output.path} />
              <PathRow label="Kịch bản" value={output.script_file} />
              <PathRow label="Phụ đề" value={output.subtitle_ass_file ?? output.subtitle_file} />
              <PathRow label="Giọng đọc" value={output.voice_file} />
              <PathRow label="Giọng WAV" value={output.normalized_voice_file} />
              <PathRow label="Nhật ký" value={output.log_file} />
            </dl>
          </article>
        );
      })}
    </div>
  );
}

function StatusBadge({ status, warnings }: { status: string; warnings: number }) {
  const normalized = status.toLowerCase();
  const classes =
    normalized === 'failed'
      ? 'border-red-200 bg-red-50 text-red-700'
      : normalized === 'warning'
        ? 'border-amber-200 bg-amber-50 text-amber-700'
        : 'border-emerald-200 bg-emerald-50 text-emerald-700';
  const label = normalized === 'warning' ? `Cảnh báo${warnings ? ` (${warnings})` : ''}` : formatStatus(normalized);

  return (
    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${classes}`}>
      {label}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md bg-surface p-3">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-1 font-semibold text-ink">{value || '-'}</dd>
    </div>
  );
}

function PathRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="grid gap-1 rounded-md bg-surface p-3 md:grid-cols-[120px_1fr_auto] md:items-center">
      <dt className="font-medium text-ink">{label}</dt>
      <dd className="break-all text-muted">{value || '-'}</dd>
      <button
        className="w-fit rounded border border-line bg-white px-3 py-1 text-xs font-semibold text-ink hover:border-brand"
        type="button"
        disabled={!value}
        onClick={() => copy(value)}
      >
        Sao chép
      </button>
    </div>
  );
}

function captionWithHashtags(output: JobOutput): string {
  const caption = (output.caption ?? '').trim();
  const hashtags = (output.hashtags ?? []).join(' ').trim();
  return [caption, hashtags].filter(Boolean).join('\n\n');
}

function openLocalPath(path?: string | null) {
  if (!path) return;
  const normalized = path.replace(/\\/g, '/');
  window.open(`file:///${encodeURI(normalized)}`, '_blank');
}

function formatId(value?: string | null) {
  if (!value) return '-';
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function shortText(value: string, limit = 220) {
  const cleaned = value.replace(/\s+/g, ' ').trim();
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, limit - 3)}...`;
}

function formatStatus(value: string) {
  const labels: Record<string, string> = {
    success: 'Thành công',
    warning: 'Có cảnh báo',
    failed: 'Thất bại',
    completed: 'Hoàn thành',
    completed_with_errors: 'Hoàn thành nhưng có lỗi',
  };
  return labels[value.toLowerCase()] ?? formatId(value);
}
