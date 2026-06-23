import { AlertTriangle, CheckCircle2, CircleHelp, RefreshCw, Server } from 'lucide-react';
import type { NormalizedSystemStatus, SystemStatusValue } from '../../services/healthApi';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';

type Props = {
  status: NormalizedSystemStatus;
  loading?: boolean;
  onRefresh?: () => void;
};

const labels: Record<SystemStatusValue | 'connected' | 'offline' | 'unknown', string> = {
  ready: 'Sẵn',
  missing: 'Thiếu',
  optional: 'Tùy chọn',
  unknown: 'Chưa rõ',
  connected: 'Kết nối',
  offline: 'Ngoại tuyến',
};

const descriptions = {
  backend: 'Bộ xử lý cục bộ dùng để quét, dựng video, nhận diện chữ, tạo giọng đọc và xuất bản.',
  ffmpeg: 'Cần để đọc, ghép, chèn phụ đề và render video.',
  ffprobe: 'Cần để đọc thông tin video trước khi xử lý.',
  translation: 'Dùng để dịch phụ đề hoặc lời dẫn sang tiếng Việt.',
  ocr: 'Chỉ cần khi video có chữ Trung trên màn hình.',
  tts: 'Chỉ cần khi tạo giọng đọc tiếng Việt.',
  outputFolder: 'Nơi lưu video, phụ đề, nhật ký và gói xuất bản.',
  localServer: 'Máy chủ cục bộ phục vụ giao diện và API trên cùng một cổng.',
};

export default function StudioSystemStatus({ status, loading, onRefresh }: Props) {
  const items = [
    { key: 'backend', label: 'Bộ xử lý', value: status.backend === 'connected' ? 'connected' : 'offline', description: descriptions.backend },
    { key: 'ffmpeg', label: 'FFmpeg', value: status.ffmpeg, description: descriptions.ffmpeg },
    { key: 'ffprobe', label: 'ffprobe', value: status.ffprobe, description: descriptions.ffprobe },
    { key: 'translation', label: 'Dịch thuật', value: status.translation, description: descriptions.translation },
    { key: 'ocr', label: 'Nhận diện chữ', value: status.ocr, description: descriptions.ocr },
    { key: 'tts', label: 'Giọng đọc', value: status.tts, description: descriptions.tts },
    { key: 'outputFolder', label: 'Thư mục đầu ra', value: status.outputFolder, description: descriptions.outputFolder },
    {
      key: 'localServer',
      label: 'Máy chủ cục bộ',
      value: status.localServer,
      description: status.singlePortUrl ? `${descriptions.localServer} ${status.singlePortUrl}` : descriptions.localServer,
    },
  ] as const;

  return (
    <GlassCard strong className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
            <Server size={18} />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">Trạng thái hệ thống</h2>
            <p className="mt-1 text-xs text-slate-400">Kiểm tra nhanh các thành phần cần để render.</p>
          </div>
        </div>
        {onRefresh ? (
          <GlassButton variant="secondary" className="min-h-9 px-3 text-xs" loading={loading} onClick={onRefresh}>
            <RefreshCw size={15} />
            Kiểm tra lại
          </GlassButton>
        ) : null}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {items.map((item) => (
          <div className="min-w-0 rounded-md border border-white/10 bg-black/15 p-2.5" key={item.key} title={item.description}>
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-white">
                <StatusIcon value={item.value} />
                <span className="truncate">{item.label}</span>
              </div>
              <GlassBadge variant={badgeVariant(item.value)}>{labels[item.value] ?? item.value}</GlassBadge>
            </div>
          </div>
        ))}
      </div>
      {status.backend !== 'connected' ? (
        <div className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
          Bộ xử lý đang tắt hoặc chưa phản hồi. Bạn vẫn có thể xem giao diện, nhưng cần bật bộ xử lý để quét và render.
        </div>
      ) : null}
    </GlassCard>
  );
}

function StatusIcon({ value }: { value: SystemStatusValue | 'connected' | 'offline' }) {
  if (value === 'ready' || value === 'connected') return <CheckCircle2 size={16} className="text-emerald-200" />;
  if (value === 'missing' || value === 'offline') return <AlertTriangle size={16} className="text-amber-200" />;
  return <CircleHelp size={16} className="text-slate-400" />;
}

function badgeVariant(value: SystemStatusValue | 'connected' | 'offline') {
  if (value === 'ready' || value === 'connected') return 'success' as const;
  if (value === 'missing' || value === 'offline') return 'warning' as const;
  return 'neutral' as const;
}
