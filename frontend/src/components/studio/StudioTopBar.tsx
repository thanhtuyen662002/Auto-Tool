import { HelpCircle, Menu, Plus, Power, Server, WifiOff } from 'lucide-react';
import GlassBadge from '../glass/GlassBadge';
import GlassButton from '../glass/GlassButton';
import StudioBreadcrumbs, { type StudioBreadcrumbItem } from './StudioBreadcrumbs';

export default function StudioTopBar({
  title,
  connected,
  breadcrumbs,
  onMenu,
  onNewBatch,
  onHelp,
  onStatus,
  onShutdown,
  shuttingDown = false,
}: {
  title: string;
  connected: boolean;
  breadcrumbs: StudioBreadcrumbItem[];
  onMenu: () => void;
  onNewBatch: () => void;
  onHelp: () => void;
  onStatus: () => void;
  onShutdown: () => void;
  shuttingDown?: boolean;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-[#070a13]/72 backdrop-blur-xl">
      <div className="flex min-h-16 items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button className="rounded-md border border-white/10 p-2 text-slate-300 hover:bg-white/8 lg:hidden" type="button" onClick={onMenu} aria-label="Mở menu">
            <Menu size={19} />
          </button>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-white sm:text-base">{title}</div>
            <StudioBreadcrumbs items={breadcrumbs} />
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" onClick={onStatus} className="hidden sm:inline-flex hover:opacity-85 transition-opacity">
            <GlassBadge variant={connected ? 'success' : 'failed'}>
              {connected ? <Server size={12} /> : <WifiOff size={12} />}
              <span className="ml-1">{connected ? 'Đã kết nối' : 'Ngoại tuyến'}</span>
            </GlassBadge>
          </button>
          <GlassButton variant="primary" className="hidden min-h-9 px-3 text-xs md:inline-flex hover:scale-[1.03] active:scale-[0.97] transition-all duration-300" onClick={onNewBatch}>
            <Plus size={15} />
            Tạo lô mới
          </GlassButton>
          <GlassButton variant="ghost" className="min-h-9 px-3 text-xs hover:scale-[1.03] active:scale-[0.97] transition-all duration-300" onClick={onHelp}>
            <HelpCircle size={15} />
            Trợ giúp
          </GlassButton>
          <GlassButton
            variant="ghost"
            className="min-h-9 px-3 text-xs text-rose-100 hover:scale-[1.03] active:scale-[0.97] transition-all duration-300"
            onClick={onShutdown}
            disabled={shuttingDown || !connected}
            title="Tắt Auto Tool"
          >
            <Power size={15} />
            Tắt
          </GlassButton>
        </div>
      </div>
    </header>
  );
}
