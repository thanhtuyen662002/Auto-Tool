import { Languages, MessageCircle, Mic, ScanText } from 'lucide-react';
import type { NormalizedSystemStatus, SystemStatusValue } from '../../services/healthApi';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import SettingsSection from './SettingsSection';

const providerRows = [
  {
    id: 'translation',
    title: 'Dịch thuật (Translation)',
    description: 'Dùng để dịch phụ đề và caption sang tiếng Việt. Nếu backend quản lý provider, UI chỉ hiển thị trạng thái.',
    icon: Languages,
  },
  {
    id: 'ocr',
    title: 'Nhận diện chữ (OCR)',
    description: 'Bạn chỉ cần OCR nếu video có chữ Trung dính trên màn hình.',
    icon: ScanText,
  },
  {
    id: 'tts',
    title: 'Giọng đọc (TTS)',
    description: 'Chỉ cần khi tạo voiceover tiếng Việt cho Silent Mode.',
    icon: Mic,
  },
] as const;

export default function ProviderSettingsCard({ status, onOpenGuide }: { status: NormalizedSystemStatus; onOpenGuide?: () => void }) {
  return (
    <SettingsSection title="Nhà cung cấp dịch vụ" description="Hiển thị trạng thái provider ở mức dễ hiểu. Cấu hình chi tiết nằm ở backend hoặc Advanced nếu cần.">
      <div className="grid gap-3">
        {providerRows.map(({ icon: Icon, ...row }) => {
          const value = status[row.id] as SystemStatusValue;
          return (
            <div className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-white/10 bg-black/15 p-4" key={row.id}>
              <div className="flex gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-white/10 bg-white/6 text-cyan-200">
                  <Icon size={18} />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold text-white">{row.title}</h3>
                    <GlassBadge variant={badgeVariant(value)}>{labelFor(value)}</GlassBadge>
                  </div>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{row.description}</p>
                </div>
              </div>
              <GlassButton variant="ghost" className="min-h-9 px-3 text-xs" onClick={onOpenGuide}>
                <MessageCircle size={14} />
                Hướng dẫn thiết lập
              </GlassButton>
            </div>
          );
        })}
      </div>
    </SettingsSection>
  );
}

function labelFor(value: SystemStatusValue): string {
  if (value === 'ready') return 'Sẵn sàng';
  if (value === 'missing') return 'Cần cấu hình';
  if (value === 'optional') return 'Không bắt buộc';
  return 'Không xác định';
}

function badgeVariant(value: SystemStatusValue) {
  if (value === 'ready') return 'success' as const;
  if (value === 'missing') return 'warning' as const;
  return 'neutral' as const;
}
