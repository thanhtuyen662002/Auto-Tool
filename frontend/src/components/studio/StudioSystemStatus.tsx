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
  ready: 'Sẵn sàng',
  missing: 'Cần cấu hình',
  optional: 'Không bắt buộc',
  unknown: 'Không xác định',
  connected: 'Connected',
  offline: 'Offline',
};

const descriptions = {
  backend: 'Server xử lý local cho scan, render, OCR, TTS và export.',
  ffmpeg: 'Cần để đọc, ghép, burn subtitle và render video.',
  ffprobe: 'Cần để đọc metadata video trước khi xử lý.',
  translation: 'Dùng để dịch phụ đề hoặc caption sang tiếng Việt.',
  ocr: 'Chỉ cần khi video có chữ Trung trên màn hình.',
  tts: 'Chỉ cần khi tạo voiceover tiếng Việt.',
  outputFolder: 'Nơi lưu video, subtitle, log và export pack.',
  localServer: 'Backend phục vụ frontend production build và API trên cùng một cổng local.',
};

export default function StudioSystemStatus({ status, loading, onRefresh }: Props) {
  const items = [
    { key: 'backend', label: 'Backend', value: status.backend === 'connected' ? 'connected' : 'offline', description: descriptions.backend },
    { key: 'ffmpeg', label: 'FFmpeg', value: status.ffmpeg, description: descriptions.ffmpeg },
    { key: 'ffprobe', label: 'ffprobe', value: status.ffprobe, description: descriptions.ffprobe },
    { key: 'translation', label: 'Translation Provider', value: status.translation, description: descriptions.translation },
    { key: 'ocr', label: 'OCR', value: status.ocr, description: descriptions.ocr },
    { key: 'tts', label: 'TTS', value: status.tts, description: descriptions.tts },
    { key: 'outputFolder', label: 'Output Folder', value: status.outputFolder, description: descriptions.outputFolder },
    {
      key: 'localServer',
      label: 'Local Server',
      value: status.localServer,
      description: status.singlePortUrl ? `${descriptions.localServer} ${status.singlePortUrl}` : descriptions.localServer,
    },
  ] as const;

  return (
    <GlassCard strong className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
            <Server size={18} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">System Status</h2>
            <p className="mt-1 text-sm text-slate-400">Trạng thái hệ thống được normalize từ backend health và dependencies.</p>
          </div>
        </div>
        {onRefresh ? (
          <GlassButton variant="secondary" loading={loading} onClick={onRefresh}>
            <RefreshCw size={15} />
            Kiểm tra lại
          </GlassButton>
        ) : null}
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {items.map((item) => (
          <div className="rounded-md border border-white/10 bg-black/15 p-4" key={item.key}>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 font-semibold text-white">
                <StatusIcon value={item.value} />
                {item.label}
              </div>
              <GlassBadge variant={badgeVariant(item.value)}>{labels[item.value] ?? item.value}</GlassBadge>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-400">{item.description}</p>
          </div>
        ))}
      </div>
      {status.backend !== 'connected' ? (
        <div className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
          Backend đang offline hoặc chưa phản hồi. Bạn vẫn có thể xem UI, nhưng cần backend để scan và render.
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
