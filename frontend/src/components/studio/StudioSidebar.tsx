import { Captions, Clapperboard, Download, FolderCheck, LayoutDashboard, RotateCcw, Settings, Sparkles, Waves, X, Inbox, FolderPlus } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import GlassBadge from '../glass/GlassBadge';

interface SidebarItem {
  to: string;
  label: string;
  helper: string;
  icon: any;
  end?: boolean;
}

const generalItems: SidebarItem[] = [
  { to: '/', label: 'Tổng quan', helper: 'Bảng điều khiển', icon: LayoutDashboard, end: true },
];

const studioItems: SidebarItem[] = [
  { to: '/douyin-download', label: 'Tải video Douyin', helper: 'Tải hàng loạt video Douyin', icon: Download },
  { to: '/douyin-reup', label: 'Reup có thoại', helper: 'Xử lý hàng loạt có thoại', icon: Clapperboard },
  { to: '/silent-mode', label: 'Reup không thoại', helper: 'Xử lý hàng loạt không thoại', icon: Waves },
  { to: '/projects/new', label: 'Tạo Video Affiliate', helper: 'Tạo video sản phẩm từ link', icon: FolderPlus },
  { to: '/import-inbox', label: 'Nhập hộp thư Shopee', helper: 'Nhập sản phẩm từ inbox', icon: Inbox },
  { to: '/results', label: 'Tác vụ & Kết quả', helper: 'Lịch sử và tiến trình render', icon: FolderCheck },
];

const utilityItems: SidebarItem[] = [
  { to: '/subtitle-review', label: 'Sửa phụ đề', helper: 'Kiểm tra & chỉnh sửa phụ đề', icon: Captions },
  { to: '/recovery', label: 'Khôi phục tác vụ', helper: 'Khôi phục các job bị gián đoạn', icon: RotateCcw },
  { to: '/settings', label: 'Cài đặt hệ thống', helper: 'Cấu hình & API Keys', icon: Settings },
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
      className={`fixed inset-y-0 left-0 z-40 flex w-[268px] flex-col border-r border-white/10 bg-[#080d19]/92 p-4 backdrop-blur-xl transition-transform lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
      aria-label="Điều hướng chính"
    >
      <div className="flex items-center justify-between gap-3 px-2 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-md border border-cyan-300/35 bg-cyan-300/10 text-cyan-200 shadow-[0_0_12px_rgba(34,211,238,0.2)] animate-pulse">
            <Sparkles size={18} />
          </div>
          <div className="min-w-0">
            <div className="truncate font-semibold text-white">Auto Tool Studio</div>
            <div className="text-xs text-slate-400">Studio video nội bộ</div>
          </div>
        </div>
        <button className="rounded-md p-2 text-slate-300 hover:bg-white/10 hover:text-white transition-colors lg:hidden" type="button" onClick={onClose} aria-label="Đóng menu">
          <X size={18} />
        </button>
      </div>

      <nav className="mt-6 grid gap-1.5 overflow-y-auto max-h-[calc(100vh-240px)] pr-1" aria-label="Studio sections">
        {generalItems.map(({ to, label, helper, icon: Icon, end }) => (
          <NavLink
            key={to}
            end={end}
            to={to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex min-h-12 items-center gap-3 rounded-md border px-3 text-sm font-medium transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/35 [&_svg]:transition-transform [&_svg]:duration-300 hover:[&_svg]:scale-110 ${
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

        <div className="mt-4 px-3 mb-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Xưởng nội dung
        </div>

        {studioItems.map(({ to, label, helper, icon: Icon, end }) => (
          <NavLink
            key={to}
            end={end}
            to={to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex min-h-12 items-center gap-3 rounded-md border px-3 text-sm font-medium transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/35 [&_svg]:transition-transform [&_svg]:duration-300 hover:[&_svg]:scale-110 ${
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

        <div className="mt-4 px-3 mb-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Công cụ hệ thống
        </div>

        {utilityItems.map(({ to, label, helper, icon: Icon, end }) => (
          <NavLink
            key={to}
            end={end}
            to={to}
            onClick={onClose}
            className={({ isActive }) =>
              `flex min-h-12 items-center gap-3 rounded-md border px-3 text-sm font-medium transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-cyan-300/35 [&_svg]:transition-transform [&_svg]:duration-300 hover:[&_svg]:scale-110 ${
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
        className="mt-auto rounded-md border border-white/10 bg-white/5 p-3 text-left transition-all duration-300 hover:border-cyan-300/25 hover:bg-white/8 focus:outline-none focus:ring-2 focus:ring-cyan-300/35 group"
      >
        <div className="text-xs font-semibold text-slate-200 group-hover:text-cyan-200 transition-colors">Auto Tool Studio</div>
        <div className="mt-1 font-mono text-[11px] text-slate-500">v{version}</div>
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-400">Backend</span>
          <GlassBadge variant={connected ? 'success' : 'failed'}>{connected ? 'Đã kết nối' : 'Ngoại tuyến'}</GlassBadge>
        </div>
      </button>
    </aside>
  );
}
