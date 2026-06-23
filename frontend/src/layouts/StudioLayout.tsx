import { useEffect, useMemo, useState } from 'react';
import { CircleAlert, RefreshCw } from 'lucide-react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import GlassButton from '../components/glass/GlassButton';
import GlassModal from '../components/glass/GlassModal';
import StudioBackground from '../components/studio/StudioBackground';
import StudioCommandCenter from '../components/studio/StudioCommandCenter';
import StudioSidebar from '../components/studio/StudioSidebar';
import StudioSystemStatus from '../components/studio/StudioSystemStatus';
import StudioTopBar from '../components/studio/StudioTopBar';
import type { StudioBreadcrumbItem } from '../components/studio/StudioBreadcrumbs';
import { getSystemStatus, offlineStatus, type NormalizedSystemStatus } from '../services/healthApi';
import { applyAppearanceSettings, getLocalUiSettings } from '../utils/localSettings';
import UpdateBanner from '../components/UpdateBanner';
import { shutdownSystem } from '../api/client';

const FALLBACK_VERSION = '1.0.0-rc1';

const pageTitles: Array<[string, string]> = [
  ['/onboarding', 'Hướng dẫn nhanh'],
  ['/recovery', 'Khôi phục tác vụ'],
  ['/help', 'Trợ giúp'],
  ['/settings/', 'Cài đặt dự án'],
  ['/settings', 'Cài đặt'],
  ['/app-settings', 'Cài đặt'],
  ['/douyin-download', 'Tải video Douyin'],
  ['/silent-mode', 'Video không thoại'],
  ['/douyin-reup', 'Video có thoại'],
  ['/subtitle-review', 'Sửa phụ đề'],
  ['/results', 'Kết quả'],
  ['/import-inbox', 'Hòm thư sản phẩm'],
  ['/projects/new', 'Tạo dự án'],
  ['/projects/', 'Cài đặt dự án'],
  ['/dashboard', 'Tổng quan'],
  ['/', 'Tổng quan'],
];

export default function StudioLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [shutdownOpen, setShutdownOpen] = useState(false);
  const [shuttingDown, setShuttingDown] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState<NormalizedSystemStatus>(() => offlineStatus());
  const title = useMemo(() => resolveTitle(location.pathname), [location.pathname]);
  const breadcrumbs = useMemo(() => buildBreadcrumbs(location.pathname, title), [location.pathname, title]);
  const version = systemStatus.version ?? FALLBACK_VERSION;
  const connected = systemStatus.backend === 'connected';

  useEffect(() => {
    applyAppearanceSettings(getLocalUiSettings());
    void refreshStatus();
  }, []);

  useEffect(() => setMenuOpen(false), [location.pathname]);

  async function refreshStatus() {
    setStatusLoading(true);
    try {
      const next = await getSystemStatus();
      const settings = getLocalUiSettings();
      setSystemStatus({ ...next, outputFolder: settings.defaultOutputFolder ? 'ready' : 'missing' });
    } finally {
      setStatusLoading(false);
    }
  }

  return (
    <div className="studio-theme min-h-screen">
      <StudioBackground />
      {menuOpen ? <button className="fixed inset-0 z-30 bg-black/60 lg:hidden" type="button" onClick={() => setMenuOpen(false)} aria-label="Đóng menu" /> : null}
      <StudioSidebar open={menuOpen} onClose={() => setMenuOpen(false)} version={version} connected={connected} onStatusClick={() => setStatusOpen(true)} />
      <div className="min-h-screen studio-content-layout">
        <StudioTopBar
          title={title}
          connected={connected}
          breadcrumbs={breadcrumbs}
          onMenu={() => setMenuOpen(true)}
          onNewBatch={() => setCommandOpen(true)}
          onHelp={() => navigate('/help')}
          onStatus={() => setStatusOpen(true)}
          onShutdown={() => setShutdownOpen(true)}
          shuttingDown={shuttingDown}
        />
        <UpdateBanner connected={connected} />
        {!connected && !statusLoading ? (
          <div className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300/25 bg-amber-300/10 px-4 py-3 text-sm text-amber-100 lg:mx-6">
            <div className="flex items-center gap-2">
              <CircleAlert size={17} />
              <span>Bộ xử lý đang tắt hoặc chưa phản hồi. Bạn vẫn có thể xem giao diện, nhưng cần bật bộ xử lý để quét, render và mở thư mục.</span>
            </div>
            <div className="flex gap-2">
              <GlassButton className="min-h-8 px-3 py-1" variant="ghost" onClick={() => void refreshStatus()}><RefreshCw size={14} /> Kiểm tra lại</GlassButton>
              <GlassButton className="min-h-8 px-3 py-1" variant="secondary" onClick={() => navigate('/help')}>Hướng dẫn</GlassButton>
            </div>
          </div>
        ) : null}
        {connected && systemStatus.recoverableJobsCount > 0 ? (
          <div className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-cyan-300/25 bg-cyan-300/10 px-4 py-3 text-sm text-cyan-100 lg:mx-6">
            <div className="flex items-center gap-2">
              <CircleAlert size={17} />
              <span>Có {systemStatus.recoverableJobsCount} tác vụ bị gián đoạn có thể khôi phục.</span>
            </div>
            <GlassButton className="min-h-8 px-3 py-1 hover:scale-[1.03] active:scale-[0.97] transition-all" variant="secondary" onClick={() => navigate('/recovery')}>Mở Trung tâm Khôi phục</GlassButton>
          </div>
        ) : null}
        <div className="studio-fade-in">
          <Outlet />
        </div>
      </div>

      <StudioCommandCenter open={commandOpen} onClose={() => setCommandOpen(false)} onSystemStatus={() => setStatusOpen(true)} />
      <GlassModal open={statusOpen} title="Trạng thái hệ thống" onClose={() => setStatusOpen(false)}>
        <StudioSystemStatus status={systemStatus} loading={statusLoading} onRefresh={() => void refreshStatus()} />
      </GlassModal>
      <GlassModal open={shutdownOpen} title="Tắt Auto Tool" onClose={() => (shuttingDown ? undefined : setShutdownOpen(false))}>
        <div className="space-y-4 text-sm text-slate-300">
          <p>Auto Tool sẽ dừng bộ xử lý cục bộ. Những tác vụ đang chạy có thể bị gián đoạn.</p>
          <div className="flex justify-end gap-2">
            <GlassButton variant="ghost" className="min-h-9 px-3 text-xs" disabled={shuttingDown} onClick={() => setShutdownOpen(false)}>
              Hủy
            </GlassButton>
            <GlassButton
              variant="primary"
              className="min-h-9 px-3 text-xs"
              loading={shuttingDown}
              onClick={() => void handleShutdown()}
            >
              Tắt ứng dụng
            </GlassButton>
          </div>
        </div>
      </GlassModal>
    </div>
  );

  async function handleShutdown() {
    setShuttingDown(true);
    try {
      await shutdownSystem();
      setShutdownOpen(false);
      window.setTimeout(() => setSystemStatus(offlineStatus()), 1200);
    } catch {
      setShuttingDown(false);
    }
  }
}

function resolveTitle(pathname: string): string {
  return pageTitles.find(([path]) => (path === '/' ? pathname === '/' : pathname.startsWith(path)))?.[1] ?? 'Auto Tool Studio';
}

function buildBreadcrumbs(pathname: string, title: string): StudioBreadcrumbItem[] {
  if (pathname === '/' || pathname === '/dashboard') return [];
  if (pathname.startsWith('/subtitle-review/') && pathname !== '/subtitle-review') return [{ label: 'Sửa phụ đề', to: '/subtitle-review' }, { label: 'Tài liệu' }];
  if (pathname.startsWith('/results/') && pathname !== '/results') return [{ label: 'Kết quả', to: '/results' }, { label: 'Lô xử lý' }];
  if (pathname.startsWith('/settings/') && pathname !== '/settings') return [{ label: 'Cài đặt', to: '/settings' }, { label: 'Dự án' }];
  if (pathname.startsWith('/projects/') && pathname !== '/projects/new') {
    const parts = pathname.split('/');
    if (parts.length > 3) {
      const sub = parts[3];
      const subLabelMap: Record<string, string> = {
        'review': 'Đánh giá video',
        'source-media': 'Video nguồn',
        'assets': 'Tài nguyên',
        'prompt-pack': 'Gói câu lệnh',
        'content': 'Nội dung',
      };
      const subLabel = subLabelMap[sub] || sub;
      const projectId = parts[2];
      return [{ label: 'Dự án', to: `/projects/${projectId}` }, { label: subLabel }];
    }
    return [{ label: 'Dự án', to: '/results' }, { label: 'Cài đặt' }];
  }
  return [{ label: title }];
}
