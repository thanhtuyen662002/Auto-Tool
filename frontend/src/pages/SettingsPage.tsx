import { useEffect, useMemo, useState } from 'react';
import GlassBadge from '../components/glass/GlassBadge';
import GlassButton from '../components/glass/GlassButton';
import GlassSelect from '../components/glass/GlassSelect';
import OnboardingHero from '../components/onboarding/OnboardingHero';
import SetupHelpModal, { type SetupHelpTopic } from '../components/onboarding/SetupHelpModal';
import AdvancedTechnicalSettings from '../components/settings/AdvancedTechnicalSettings';
import ApiKeysSettingsCard from '../components/settings/ApiKeysSettingsCard';
import AppearanceSettingsCard from '../components/settings/AppearanceSettingsCard';
import DataManagementSettings from '../components/settings/DataManagementSettings';
import LocalAppSettingsCard from '../components/settings/LocalAppSettingsCard';
import PathSettingsCard from '../components/settings/PathSettingsCard';
import ProviderSettingsCard from '../components/settings/ProviderSettingsCard';
import SettingsLayout, { type SettingsTab } from '../components/settings/SettingsLayout';
import SettingsSection from '../components/settings/SettingsSection';
import SystemStatusCard from '../components/settings/SystemStatusCard';
import { getSystemStatus, offlineStatus, type NormalizedSystemStatus } from '../services/healthApi';
import {
  getLocalUiSettings,
  markOnboardingSeen,
  saveLocalUiSettings,
  type DefaultWorkflow,
} from '../utils/localSettings';

export default function SettingsPage() {
  const initialSettings = useMemo(() => getLocalUiSettings(), []);
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [status, setStatus] = useState<NormalizedSystemStatus>(() => offlineStatus());
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [defaultWorkflow, setDefaultWorkflow] = useState<DefaultWorkflow>(initialSettings.defaultWorkflow);
  const [language, setLanguage] = useState('vi');
  const [helpTopic, setHelpTopic] = useState<SetupHelpTopic | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void refreshStatus();
  }, []);

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

  function saveGeneral() {
    saveLocalUiSettings({ defaultWorkflow });
    setMessage('Đã lưu General settings.');
  }

  return (
    <main className="studio-page grid gap-6">
      <section>
        <GlassBadge variant="neutral">Settings</GlassBadge>
        <h1 className="mt-3 text-3xl font-semibold text-white">Cài đặt</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
          Cấu hình những thứ thường dùng trước. Các thiết lập kỹ thuật được gom vào Advanced để màn hình không rối.
        </p>
      </section>

      <SettingsLayout activeTab={activeTab} onTabChange={setActiveTab}>
        {activeTab === 'general' ? (
          <SettingsSection title="General" description="Chọn workflow mặc định và ngôn ngữ hiển thị cho trải nghiệm hằng ngày.">
            <div className="grid gap-4 lg:grid-cols-3">
              <GlassSelect label="Default workflow" value={defaultWorkflow} onChange={(event) => setDefaultWorkflow(event.target.value as DefaultWorkflow)}>
                <option value="douyin">Video có thoại</option>
                <option value="silent">Video không thoại</option>
                <option value="subtitle">Sửa phụ đề</option>
              </GlassSelect>
              <GlassSelect label="Default preset" value="safe-review" disabled>
                <option value="safe-review">Theo workflow đã chọn</option>
              </GlassSelect>
              <GlassSelect label="Language" value={language} onChange={(event) => setLanguage(event.target.value)}>
                <option value="vi">Tiếng Việt</option>
                <option value="vi-en">Tiếng Việt + English labels</option>
              </GlassSelect>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <GlassButton variant="primary" onClick={saveGeneral}>Lưu General</GlassButton>
              <GlassButton variant="ghost" onClick={() => { markOnboardingSeen(); setMessage('Đã đánh dấu onboarding là đã xem.'); }}>Ẩn onboarding banner</GlassButton>
            </div>
            {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
          </SettingsSection>
        ) : null}

        {activeTab === 'api_keys' ? <ApiKeysSettingsCard /> : null}

        {activeTab === 'paths' ? <PathSettingsCard onSaved={() => void refreshStatus()} /> : null}

        {activeTab === 'local_app' ? <LocalAppSettingsCard /> : null}

        {activeTab === 'data_management' ? <DataManagementSettings /> : null}

        {activeTab === 'providers' ? (
          <div className="grid gap-5">
            <ProviderSettingsCard status={status} onOpenGuide={() => setHelpTopic('translation')} />
            <SystemStatusCard status={status} loading={loadingStatus} onRefresh={() => void refreshStatus()} />
          </div>
        ) : null}

        {activeTab === 'appearance' ? <AppearanceSettingsCard /> : null}

        {activeTab === 'advanced' ? <AdvancedTechnicalSettings /> : null}

        {activeTab === 'about' ? (
          <div className="grid gap-5">
            <SettingsSection title="About" description="Auto Tool Studio là app local để xử lý video, không phải dashboard backend rời rạc.">
              <div className="grid gap-3 text-sm text-slate-300">
                <div className="flex justify-between gap-3 rounded-md border border-white/10 bg-black/15 p-3">
                  <span>Version</span>
                  <span className="font-mono text-slate-100">v{status.version ?? '1.0.0-rc1'}</span>
                </div>
                <div className="flex justify-between gap-3 rounded-md border border-white/10 bg-black/15 p-3">
                  <span>Capabilities</span>
                  <span>{status.capabilities ? Object.keys(status.capabilities).join(', ') || 'Không xác định' : 'Không xác định'}</span>
                </div>
                <div className="rounded-md border border-white/10 bg-black/15 p-3 leading-6">
                  Dữ liệu xử lý trên máy local. UI không lưu API key hoặc thông tin nhạy cảm vào localStorage.
                </div>
              </div>
            </SettingsSection>
            <OnboardingHero onSkip={() => { markOnboardingSeen(); setMessage('Đã bỏ qua onboarding.'); }} />
          </div>
        ) : null}
      </SettingsLayout>

      <SetupHelpModal topic={helpTopic} onClose={() => setHelpTopic(null)} />
    </main>
  );
}
