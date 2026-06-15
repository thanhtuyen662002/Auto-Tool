import { RotateCcw, Settings2, X } from 'lucide-react';
import type { ReactNode } from 'react';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';

export default function StartAdvancedSettingsDrawer({
  open,
  custom,
  children,
  onOpen,
  onClose,
  onReset,
}: {
  open: boolean;
  custom: boolean;
  children: ReactNode;
  onOpen: () => void;
  onClose: () => void;
  onReset: () => void;
}) {
  return (
    <>
      <button
        className="inline-flex min-h-10 items-center gap-2 rounded-md border border-white/15 bg-white/8 px-4 py-2 text-sm font-semibold text-white hover:border-cyan-300/45"
        type="button"
        onClick={onOpen}
      >
        <Settings2 size={16} />
        Cài đặt nâng cao
        {custom ? <GlassBadge variant="warning">Đã tùy chỉnh</GlassBadge> : null}
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/55" role="dialog" aria-modal="true" aria-label="Cài đặt nâng cao">
          <button className="hidden flex-1 cursor-default md:block" type="button" aria-label="Đóng cài đặt nâng cao" onClick={onClose} />
          <aside className="h-full w-full max-w-3xl overflow-auto border-l border-white/10 bg-slate-950/95 p-5 shadow-2xl backdrop-blur">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-white">Cài đặt nâng cao</h2>
                <p className="mt-1 text-sm text-slate-400">Các mục kỹ thuật được để riêng để màn start đơn giản hơn.</p>
              </div>
              <button className="rounded-md p-2 text-slate-300 hover:bg-white/10 hover:text-white" type="button" onClick={onClose} aria-label="Đóng">
                <X size={18} />
              </button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {['Phụ đề', 'Nhận diện giọng nói', 'Nhận diện chữ', 'Âm thanh', 'Đầu ra', 'Kiểm tra cuối', 'Gói xuất bản'].map((item) => (
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300" key={item}>{item}</span>
              ))}
            </div>
            <div className="mt-5">
              <GlassButton variant="secondary" onClick={onReset}>
                <RotateCcw size={16} />
                Khôi phục theo preset
              </GlassButton>
            </div>
            <div className="mt-5 grid gap-5">{children}</div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
