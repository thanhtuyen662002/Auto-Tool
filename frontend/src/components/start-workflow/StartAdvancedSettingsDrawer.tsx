import { RotateCcw, X } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';

export default function StartAdvancedSettingsDrawer({
  open,
  custom,
  children,
  onClose,
  onReset,
}: {
  open: boolean;
  custom: boolean;
  children: ReactNode;
  onClose: () => void;
  onReset: () => void;
}) {
  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <>
      {open ? (
        <div className="fixed inset-0 z-50 flex justify-end overflow-hidden bg-black/55" role="dialog" aria-modal="true" aria-label="Cài đặt nâng cao">
          <button className="hidden flex-1 cursor-default md:block" type="button" aria-label="Đóng cài đặt nâng cao" onClick={onClose} />
          <aside className="flex h-screen max-h-screen w-full max-w-3xl flex-col overflow-hidden border-l border-white/10 bg-slate-950/95 shadow-2xl backdrop-blur">
            <div className="border-b border-white/10 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-white">Cài đặt nâng cao</h2>
                    {custom ? <GlassBadge variant="warning">Đã tùy chỉnh</GlassBadge> : null}
                  </div>
                  <p className="mt-1 text-sm text-slate-400">Tinh chỉnh phụ đề, nhận diện giọng nói, OCR, âm thanh, overlay và giới hạn batch.</p>
                </div>
                <button className="rounded-md p-2 text-slate-300 hover:bg-white/10 hover:text-white" type="button" onClick={onClose} aria-label="Đóng">
                  <X size={18} />
                </button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {['Phụ đề', 'Giọng nói', 'OCR', 'Âm thanh', 'Overlay', 'Đầu ra', 'Batch lớn'].map((item) => (
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300" key={item}>{item}</span>
                ))}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-14 pt-5">
              <div className="grid gap-5 pb-4">
                <GlassButton variant="secondary" onClick={onReset}>
                  <RotateCcw size={16} />
                  Khôi phục theo preset
                </GlassButton>
                {children}
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
