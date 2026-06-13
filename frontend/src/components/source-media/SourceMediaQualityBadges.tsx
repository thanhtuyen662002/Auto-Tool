import type { SourceBrowserMediaItem } from '../../types/project';

const FLAG_LABELS: Record<string, string> = {
  too_short: 'Quá ngắn',
  too_long: 'Quá dài',
  low_resolution: 'Độ phân giải thấp',
  horizontal_video: 'Video ngang',
  square_video: 'Video vuông',
  no_audio: 'Không có audio',
  unreadable: 'Không đọc được',
  duplicate_name: 'Trùng tên',
  very_large_file: 'File lớn',
};

export default function SourceMediaQualityBadges({ item }: { item: SourceBrowserMediaItem }) {
  const flags = item.quality_flags || [];
  if (!flags.length && item.status === 'valid') {
    return <span className="rounded-full border border-emerald-300/30 bg-emerald-300/10 px-2 py-0.5 text-xs text-emerald-100">Tốt</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {flags.slice(0, 4).map((flag) => (
        <span key={flag} className="rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-0.5 text-xs text-amber-100">
          {FLAG_LABELS[flag] || flag}
        </span>
      ))}
      {flags.length > 4 ? (
        <span className="rounded-full border border-white/15 bg-white/8 px-2 py-0.5 text-xs text-slate-300">+{flags.length - 4}</span>
      ) : null}
    </div>
  );
}
