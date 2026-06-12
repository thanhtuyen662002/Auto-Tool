import { AlertTriangle, CheckCircle2, CircleHelp, Info, Wrench } from 'lucide-react';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import GlassCard from '../glass/GlassCard';
import type { SystemStatusValue } from '../../services/healthApi';
import type { SetupHelpTopic } from './SetupHelpModal';

type Props = {
  title: string;
  description: string;
  status: SystemStatusValue | 'connected' | 'offline';
  topic: SetupHelpTopic;
  optional?: boolean;
  onHelp: (topic: SetupHelpTopic) => void;
  onRetry?: () => void;
};

const labels: Record<string, string> = {
  ready: 'Sẵn sàng',
  connected: 'Đã kết nối',
  missing: 'Cần cấu hình',
  offline: 'Offline',
  optional: 'Không bắt buộc',
  unknown: 'Không xác định',
};

export default function SetupRequirementCard({ title, description, status, topic, optional, onHelp, onRetry }: Props) {
  const tone = status === 'ready' || status === 'connected' ? 'success' : status === 'missing' || status === 'offline' ? 'warning' : 'neutral';
  const Icon = status === 'ready' || status === 'connected' ? CheckCircle2 : status === 'missing' || status === 'offline' ? AlertTriangle : optional ? Info : CircleHelp;

  return (
    <GlassCard className="p-4" strong>
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-white/10 bg-black/20 text-cyan-200">
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold text-white">{title}</h3>
            <GlassBadge variant={tone}>{labels[status] ?? status}</GlassBadge>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-300">{description}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <GlassButton variant="ghost" className="min-h-9 px-3 text-xs" onClick={() => onHelp(topic)}>
              <Wrench size={14} />
              Hướng dẫn setup
            </GlassButton>
            {onRetry ? (
              <GlassButton variant="secondary" className="min-h-9 px-3 text-xs" onClick={onRetry}>
                Kiểm tra lại
              </GlassButton>
            ) : null}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
