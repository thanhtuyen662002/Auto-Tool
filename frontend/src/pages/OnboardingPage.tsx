import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import FirstRunChecklist from '../components/onboarding/FirstRunChecklist';
import OnboardingHero from '../components/onboarding/OnboardingHero';
import WorkflowGuideCards from '../components/onboarding/WorkflowGuideCards';
import PathSettingsCard from '../components/settings/PathSettingsCard';
import GlassButton from '../components/glass/GlassButton';
import GlassCard from '../components/glass/GlassCard';
import { getSystemStatus, offlineStatus, type NormalizedSystemStatus } from '../services/healthApi';
import { markOnboardingSeen } from '../utils/localSettings';

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<NormalizedSystemStatus>(() => offlineStatus());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void refreshStatus();
  }, []);

  async function refreshStatus() {
    setLoading(true);
    try {
      setStatus(await getSystemStatus());
    } finally {
      setLoading(false);
    }
  }

  function skip() {
    markOnboardingSeen();
    navigate('/');
  }

  return (
    <main className="studio-page grid gap-6">
      <OnboardingHero onSkip={skip} />

      <section className="grid gap-3 sm:grid-cols-4">
        {['Chọn workflow', 'Kiểm tra hệ thống', 'Chọn output folder', 'Chạy batch test'].map((step, index) => (
          <div className="rounded-md border border-white/10 bg-black/18 p-4" key={step}>
            <div className="text-xs font-semibold uppercase text-cyan-200">Bước {index + 1}</div>
            <div className="mt-2 text-sm font-semibold text-white">{step}</div>
          </div>
        ))}
      </section>

      <WorkflowGuideCards />
      <FirstRunChecklist status={status} onRefresh={() => void refreshStatus()} prominent />
      {loading ? <div className="text-sm text-slate-400">Đang kiểm tra hệ thống...</div> : null}
      <PathSettingsCard />

      <GlassCard strong className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-white">Sẵn sàng chạy batch test nhỏ</h2>
            <p className="mt-1 text-sm leading-6 text-slate-400">
              Chọn 1-3 video mẫu trước để làm quen với flow review, results và export pack.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/douyin-reup" onClick={markOnboardingSeen}>
              <GlassButton variant="primary">Video có thoại</GlassButton>
            </Link>
            <Link to="/silent-mode" onClick={markOnboardingSeen}>
              <GlassButton variant="secondary">Video không thoại</GlassButton>
            </Link>
            <GlassButton variant="ghost" onClick={skip}>Bỏ qua</GlassButton>
          </div>
        </div>
      </GlassCard>
    </main>
  );
}
