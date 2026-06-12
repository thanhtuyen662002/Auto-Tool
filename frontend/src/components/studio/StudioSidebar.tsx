import { Captions, Clapperboard, FolderCheck, LayoutDashboard, Settings, Sparkles, Waves, X } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import GlassBadge from '../glass/GlassBadge';

const items = [
  { to: '/', label: 'Tổng quan', helper: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/douyin-reup', label: 'Video có thoại', helper: 'Douyin Reup', icon: Clapperboard },
  { to: '/silent-mode', label: 'Video không thoại', helper: 'Silent Mode', icon: Waves },
  { to: '/subtitle-review', label: 'Sửa phụ đề', helper: 'Subtitle Review', icon: Captions },
  { to: '/results', label: 'Kết quả', helper: 'Results', icon: FolderCheck },
  { to: '/settings', label: 'Cài đặt', helper: 'Settings', icon: Settings },
];

export default function StudioSidebar({
  open,
  onClose,
  version,
  connected,
  onStatusClick,
}: {
  open: boolean;
  onClose: () => void;
  version: string;
  connected: boolean;
  onStatusClick: () => void;
}) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col border-r border-white/10 bg-[#080d19]/92 p-4 backdrop-blur-xl transition-transform lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      aria-label="Điều hướng chính"
    >
      <div className="flex items-center justify-between gap-3 px-2 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md border border-cyan-300/35 bg-cyan-300/10 text-cyan-200">
            <Sparkles size={18} />
          </div>
          <div className="min-w-0">
            <div className="truncate font-semibold text-white">Auto Tool Studio</div>
            <div className="text-xs text-slate-400">Local video studio</div>
          </div>
        </div>
        <button className="rounded-md p-2 text-slate-300 hover:bg-white/10 lg:hidden" type="button" onClick={onClose} aria-label="Đóng menu">
          <X size={18} />
        </button>
      </div>

      <nav className="mt-6 grid gap-1.5" aria-label="Studio sections">
        {items.map(({ to, label, helper, icon: Icon, end }) => (
          <NavLink
            key={to}
            end={end}
            to={to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex min-h-12 items-center gap-3 rounded-md border px-3 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-cyan-300/35 ${
                isActive
                  ? 'border-cyan-300/35 bg-cyan-300/12 text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.12)]'
                  : 'border-transparent text-slate-300 hover:bg-white/7 hover:text-white'
              }`
            }
          >
            <Icon size={18} />
            <span className="min-w-0">
              <span className="block truncate">{label}</span>
              <span className="block truncate text-[11px] font-normal text-slate-500">{helper}</span>
            </span>
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        onClick={onStatusClick}
        className="mt-auto rounded-md border border-white/10 bg-white/5 p-3 text-left transition hover:border-cyan-300/25 hover:bg-white/8 focus:outline-none focus:ring-2 focus:ring-cyan-300/35"
      >
        <div className="text-xs font-semibold text-slate-200">Auto Tool Studio</div>
        <div className="mt-1 font-mono text-[11px] text-slate-500">v{version}</div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Backend</span>
          <GlassBadge variant={connected ? 'success' : 'failed'}>{connected ? 'Connected' : 'Offline'}</GlassBadge>
        </div>
      </button>
    </aside>
  );
}
