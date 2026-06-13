import { ArrowRight, Sparkles, ShoppingBag } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listProjects } from '../api/client';
import GlassBadge from '../components/glass/GlassBadge';
import GlassButton from '../components/glass/GlassButton';
import GlassCard from '../components/glass/GlassCard';
import FirstRunChecklist from '../components/onboarding/FirstRunChecklist';
import WorkflowGuideCards from '../components/onboarding/WorkflowGuideCards';
import StudioQuickActions from '../components/studio/StudioQuickActions';
import StudioRecentOutputs from '../components/studio/StudioRecentOutputs';
import StudioRecentProjects from '../components/studio/StudioRecentProjects';
import StudioSystemStatus from '../components/studio/StudioSystemStatus';
import { getSystemStatus, offlineStatus, type NormalizedSystemStatus } from '../services/healthApi';
import type { ProjectListItem } from '../types/project';
import { getLocalUiSettings, markOnboardingSeen } from '../utils/localSettings';

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [status, setStatus] = useState<NormalizedSystemStatus>(() => offlineStatus());
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [showFirstRun, setShowFirstRun] = useState(() => !getLocalUiSettings().onboardingSeen);

  const pageSize = 5;

  async function loadProjects(page: number) {
    try {
      const offset = (page - 1) * pageSize;
      const response = await listProjects(pageSize, offset);
      setProjects(response.items || []);
      setTotalPages(Math.ceil((response.total || 0) / pageSize));
    } catch {
      setProjects([]);
      setTotalPages(1);
    }
  }

  useEffect(() => {
    void loadProjects(currentPage);
    void refreshStatus();
  }, [currentPage]);


  async function refreshStatus() {
    setLoadingStatus(true);
    try {
      const next = await getSystemStatus();
      const settings = getLocalUiSettings();
      setStatus({ ...next, outputFolder: settings.defaultOutputFolder ? 'ready' : 'missing' });
    } finally {
      setLoadingStatus(false);
    }
  }

  function dismissOnboarding() {
    markOnboardingSeen();
    setShowFirstRun(false);
  }

  const shouldShowFirstRun = showFirstRun && projects.length === 0;

  return (
    <main className="studio-page grid gap-6">
      <section className="py-3 sm:py-6">
        <GlassBadge variant="ready">Auto Tool Studio</GlassBadge>
        <h1 className="mt-4 max-w-3xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
          Bắt đầu tạo video đầu tiên của bạn
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-300">
          Chọn workflow phù hợp, Auto Tool sẽ lo phần xử lý phía sau và chỉ đưa các quyết định cần thiết ra trước bạn.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/douyin-reup">
            <GlassButton variant="primary">
              Bắt đầu với Video có thoại
              <ArrowRight size={16} />
            </GlassButton>
          </Link>
          <Link to="/silent-mode">
            <GlassButton variant="secondary">Bắt đầu với Video không thoại</GlassButton>
          </Link>
          <Link to="/projects/new">
            <GlassButton variant="secondary" className="border-purple-500/30 text-purple-200 hover:text-white hover:bg-purple-500/10">
              Tạo Video Affiliate
            </GlassButton>
          </Link>
        </div>
      </section>

      {shouldShowFirstRun ? (
        <GlassCard strong className="border-cyan-300/35 p-5 glow-primary">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-cyan-300/25 bg-cyan-300/10 text-cyan-200">
                <Sparkles size={18} />
              </div>
              <div>
                <h2 className="font-semibold text-white">Bạn mới dùng Auto Tool?</h2>
                <p className="mt-1 text-sm leading-6 text-slate-300">Làm theo 3 bước để chạy batch đầu tiên: chọn workflow, kiểm tra hệ thống, chọn output folder.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to="/onboarding">
                <GlassButton variant="primary">Xem hướng dẫn nhanh</GlassButton>
              </Link>
              <GlassButton variant="ghost" onClick={dismissOnboarding}>Bỏ qua</GlassButton>
            </div>
          </div>
        </GlassCard>
      ) : null}

      <GlassCard hover strong className="p-5 border-purple-500/30">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-purple-300/25 bg-purple-300/10 text-purple-200">
              <ShoppingBag size={18} />
            </div>
            <div>
              <h2 className="font-semibold text-white">Tạo Video Affiliate</h2>
              <p className="mt-1 text-sm text-slate-300">
                Tạo video từ nhiều video nguồn phù hợp Shopee/TikTok Shop
              </p>
            </div>
          </div>
          <Link to="/projects/new">
            <GlassButton variant="secondary" className="border-purple-500/30 text-purple-200 hover:text-white hover:bg-purple-500/10">
              Tạo dự án
            </GlassButton>
          </Link>
        </div>
      </GlassCard>

      <WorkflowGuideCards />
      <StudioQuickActions />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.7fr)]">
        <StudioRecentProjects
          projects={projects}
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
        <StudioSystemStatus status={status} loading={loadingStatus} onRefresh={() => void refreshStatus()} />
      </section>


      {shouldShowFirstRun ? <FirstRunChecklist status={status} onRefresh={() => void refreshStatus()} /> : null}

      <StudioRecentOutputs />
    </main>
  );
}
