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

const FALLBACK_VERSION = '1.0.0-rc1';

const pageTitles: Array<[string, string]> = [
  ['/onboarding', 'Onboarding'],
  ['/recovery', 'Khôi phục job'],
  ['/help', 'Trợ giúp'],
  ['/settings/', 'Cài đặt project'],
  ['/settings', 'Cài đặt'],
  ['/app-settings', 'Cài đặt'],
  ['/silent-mode', 'Video không thoại'],
  ['/douyin-reup', 'Video có thoại'],
  ['/subtitle-review', 'Sửa phụ đề'],
  ['/results', 'Kết quả'],
  ['/projects/new', 'Tạo dự án'],
  ['/dashboard', 'Tổng quan'],
  ['/', 'Tổng quan'],
];

export default function StudioLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
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
      <div className="min-h-screen lg:pl-[248px]">
        <StudioTopBar
          title={title}
          connected={connected}
          breadcrumbs={breadcrumbs}
          onMenu={() => setMenuOpen(true)}
          onNewBatch={() => setCommandOpen(true)}
          onHelp={() => navigate('/help')}
          onStatus={() => setStatusOpen(true)}
        />
        {!connected && !statusLoading ? (
          <div className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300/25 bg-amber-300/10 px-4 py-3 text-sm text-amber-100 lg:mx-6">
            <div className="flex items-center gap-2">
              <CircleAlert size={17} />
              <span>Backend đang offline. Bạn vẫn có thể xem UI, nhưng cần backend để scan, render và mở thư mục.</span>
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
              <span>Có {systemStatus.recoverableJobsCount} job bị gián đoạn có thể khôi phục.</span>
            </div>
            <GlassButton className="min-h-8 px-3 py-1" variant="secondary" onClick={() => navigate('/recovery')}>Open Recovery Center</GlassButton>
          </div>
        ) : null}
        <div className="studio-fade-in">
          <Outlet />
        </div>
      </div>

      <StudioCommandCenter open={commandOpen} onClose={() => setCommandOpen(false)} onSystemStatus={() => setStatusOpen(true)} />
      <GlassModal open={statusOpen} title="System Status" onClose={() => setStatusOpen(false)}>
        <StudioSystemStatus status={systemStatus} loading={statusLoading} onRefresh={() => void refreshStatus()} />
      </GlassModal>
    </div>
  );
}

function resolveTitle(pathname: string): string {
  return pageTitles.find(([path]) => (path === '/' ? pathname === '/' : pathname.startsWith(path)))?.[1] ?? 'Auto Tool Studio';
}

function buildBreadcrumbs(pathname: string, title: string): StudioBreadcrumbItem[] {
  if (pathname === '/' || pathname === '/dashboard') return [];
  if (pathname.startsWith('/subtitle-review/') && pathname !== '/subtitle-review') return [{ label: 'Sửa phụ đề', to: '/subtitle-review' }, { label: 'Document' }];
  if (pathname.startsWith('/results/') && pathname !== '/results') return [{ label: 'Kết quả', to: '/results' }, { label: 'Batch' }];
  if (pathname.startsWith('/settings/') && pathname !== '/settings') return [{ label: 'Cài đặt', to: '/settings' }, { label: 'Project' }];
  return [{ label: title }];
}
