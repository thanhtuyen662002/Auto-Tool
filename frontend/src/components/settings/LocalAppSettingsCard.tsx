import { CheckCircle2, CircleAlert, Copy, RefreshCw, RotateCcw, Save, Server } from 'lucide-react';
import { useEffect, useState } from 'react';
import {
  DEFAULT_LOCAL_APP_CONFIG,
  getFrontendStatus,
  getLocalAppConfig,
  getLocalSystemCheck,
  saveLocalAppConfig,
  type LocalAppConfig,
  type LocalFrontendStatus,
  type LocalSystemCheck,
} from '../../services/localAppApi';
import { saveLocalUiSettings } from '../../utils/localSettings';
import { copyText } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import GlassInput from '../glass/GlassInput';
import SettingsSection from './SettingsSection';

export default function LocalAppSettingsCard() {
  const [config, setConfig] = useState<LocalAppConfig>(DEFAULT_LOCAL_APP_CONFIG);
  const [systemCheck, setSystemCheck] = useState<LocalSystemCheck | null>(null);
  const [frontendStatus, setFrontendStatus] = useState<LocalFrontendStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getLocalAppConfig(), getFrontendStatus().catch(() => null)])
      .then(([loadedConfig, loadedStatus]) => {
        setConfig(loadedConfig);
        setFrontendStatus(loadedStatus);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : 'Không thể tải Local App settings.'))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setLoading(true);
    setMessage(null);
    try {
      const saved = await saveLocalAppConfig(config);
      setConfig(saved);
      syncLocalFolderDefaults(saved);
      setMessage('Đã lưu Local App settings.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể lưu Local App settings.');
    } finally {
      setLoading(false);
    }
  }

  async function reset() {
    setConfig(DEFAULT_LOCAL_APP_CONFIG);
    setLoading(true);
    try {
      const saved = await saveLocalAppConfig(DEFAULT_LOCAL_APP_CONFIG);
      setConfig(saved);
      syncLocalFolderDefaults(saved);
      setMessage('Đã khôi phục cấu hình mặc định.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Không thể reset cấu hình.');
    } finally {
      setLoading(false);
    }
  }

  async function checkSystem() {
    setChecking(true);
    setMessage(null);
    try {
      const [nextSystemCheck, nextFrontendStatus] = await Promise.all([
        getLocalSystemCheck(),
        getFrontendStatus(),
      ]);
      setSystemCheck(nextSystemCheck);
      setFrontendStatus(nextFrontendStatus);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Backend đang offline.');
    } finally {
      setChecking(false);
    }
  }

  async function copyProductionUrl() {
    await copyText(frontendStatus?.data.single_port_url || config.single_port_url);
    setMessage('Đã copy production URL.');
  }

  return (
    <div className="grid gap-5">
      <SettingsSection title="Local App" description="Cấu hình launcher, thư mục mặc định và các thao tác desktop trên máy hiện tại.">
        <div className="grid gap-4 lg:grid-cols-3">
          <GlassInput label="Default source folder" value={config.default_source_folder} onChange={(event) => setConfig({ ...config, default_source_folder: event.target.value })} />
          <GlassInput label="Default output folder" value={config.default_output_folder} onChange={(event) => setConfig({ ...config, default_output_folder: event.target.value })} />
          <GlassInput label="Default music folder" value={config.default_music_folder} onChange={(event) => setConfig({ ...config, default_music_folder: event.target.value })} />
          <GlassInput label="Backend host" value={config.backend_host} onChange={(event) => setConfig({ ...config, backend_host: event.target.value })} />
          <GlassInput label="Backend port" type="number" min={1} max={65535} value={config.backend_port} onChange={(event) => setConfig({ ...config, backend_port: Number(event.target.value) })} />
          <GlassInput label="Recent items" type="number" min={1} max={20} value={config.max_recent_items} onChange={(event) => setConfig({ ...config, max_recent_items: Number(event.target.value) })} />
          <GlassInput label="Single port URL" value={config.single_port_url} onChange={(event) => setConfig({ ...config, single_port_url: event.target.value })} />
          <GlassInput label="Frontend dist path" value={config.frontend_dist_path} onChange={(event) => setConfig({ ...config, frontend_dist_path: event.target.value })} />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Toggle label="Tự mở trình duyệt khi app khởi động" checked={config.auto_open_browser} onChange={(checked) => setConfig({ ...config, auto_open_browser: checked })} />
          <Toggle label="Cho phép Open Folder / Reveal File" checked={config.enable_open_folder} onChange={(checked) => setConfig({ ...config, enable_open_folder: checked })} />
          <Toggle label="Production single port" checked={config.production_single_port} onChange={(checked) => setConfig({ ...config, production_single_port: checked })} />
          <Toggle label="Backend serve frontend build" checked={config.serve_frontend_dist} onChange={(checked) => setConfig({ ...config, serve_frontend_dist: checked })} />
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <GlassButton variant="primary" loading={loading} onClick={() => void save()}><Save size={16} /> Lưu</GlassButton>
          <GlassButton variant="secondary" onClick={() => void reset()}><RotateCcw size={16} /> Reset</GlassButton>
          <GlassButton variant="ghost" loading={checking} onClick={() => void checkSystem()}><RefreshCw size={16} /> Kiểm tra hệ thống</GlassButton>
        </div>
        {message ? <p className="mt-3 text-sm text-cyan-100">{message}</p> : null}
      </SettingsSection>

      <SettingsSection title="Production Server" description="Trạng thái frontend production build được phục vụ trực tiếp bởi FastAPI.">
        <div className="grid gap-3 md:grid-cols-3">
          <StatusValue label="Run mode" value={frontendStatus?.data.mode === 'production_single_port' ? 'Production Single Port' : frontendStatus ? 'Development' : 'Unknown'} ready={frontendStatus?.data.mode === 'production_single_port'} />
          <StatusValue label="Frontend" value={frontendStatus?.data.index_html_exists ? 'Build found' : 'Missing'} ready={Boolean(frontendStatus?.data.index_html_exists)} />
          <StatusValue label="Local Server" value={frontendStatus?.data.served_by_backend ? 'Ready' : 'Unknown'} ready={Boolean(frontendStatus?.data.served_by_backend)} />
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-white/10 bg-black/15 p-4">
          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase text-slate-500">Single port URL</div>
            <div className="mt-1 truncate font-mono text-sm text-cyan-100">{frontendStatus?.data.single_port_url || config.single_port_url}</div>
          </div>
          <GlassButton variant="secondary" onClick={() => void copyProductionUrl()}><Copy size={15} /> Copy production URL</GlassButton>
        </div>
        {frontendStatus && !frontendStatus.success ? (
          <div className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
            Frontend production build chưa có. Hãy chạy scripts/build_frontend hoặc scripts/start_local_prod.
          </div>
        ) : null}
      </SettingsSection>

      {systemCheck ? (
        <SettingsSection title={`System Check · ${systemCheck.platform}`} description={systemCheck.ready ? 'Các thành phần bắt buộc đã sẵn sàng.' : 'Còn thành phần bắt buộc cần cài đặt hoặc cấu hình.'}>
          <div className="grid gap-2 md:grid-cols-2">
            {systemCheck.checks.map((item) => {
              const ready = item.status === 'ready';
              return (
                <div key={item.name} className="flex min-w-0 items-start gap-3 rounded-md border border-white/10 bg-black/15 p-3">
                  {ready ? <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-300" size={17} /> : <CircleAlert className="mt-0.5 shrink-0 text-amber-300" size={17} />}
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-white">{item.name}</div>
                    <div className="text-xs text-slate-400">{item.message}</div>
                    {item.path ? <div className="mt-1 truncate font-mono text-[11px] text-slate-500" title={item.path}>{item.path}</div> : null}
                  </div>
                </div>
              );
            })}
          </div>
        </SettingsSection>
      ) : null}
    </div>
  );
}

function StatusValue({ label, value, ready }: { label: string; value: string; ready: boolean }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 p-4">
      <Server size={17} className={ready ? 'text-emerald-300' : 'text-slate-500'} />
      <div>
        <div className="text-xs text-slate-500">{label}</div>
        <div className="mt-0.5 text-sm font-semibold text-white">{value}</div>
      </div>
    </div>
  );
}

function syncLocalFolderDefaults(config: LocalAppConfig) {
  saveLocalUiSettings({
    defaultSourceFolder: config.default_source_folder,
    defaultOutputFolder: config.default_output_folder,
    defaultMusicFolder: config.default_music_folder,
  });
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex min-h-12 items-center justify-between gap-4 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
      <span>{label}</span>
      <input className="h-4 w-4 accent-cyan-300" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}
