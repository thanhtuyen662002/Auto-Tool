import { useEffect, useState } from 'react';
import { CheckCircle2, Cpu, Info, KeyRound } from 'lucide-react';
import { getAppSettings, getGoogleCloudTTSVoices, getSystemDependencies, saveAppSettings } from '../api/client';
import ApiErrorBox from '../components/ApiErrorBox';
import GlassBadge from '../components/glass/GlassBadge';
import GlassCard from '../components/glass/GlassCard';
import PathInput from '../components/PathInput';
import TextArea from '../components/TextArea';
import TextInput from '../components/TextInput';
import type { AppSettings, SystemDependencyStatusResponse } from '../types/project';

const EMPTY_SETTINGS: AppSettings = {
  gemini_api_keys: [],
  google_tts_credentials_json_path: '',
  google_tts_api_key: '',
  google_tts_access_token: '',
  google_tts_favorite_voices: [],
  google_tts_preview_text: 'Xin chào, đây là giọng đọc thử của Auto Tool.',
  favorite_music_paths: [],
};

export default function AppSettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(EMPTY_SETTINGS);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingVoices, setTestingVoices] = useState(false);
  const [dependencies, setDependencies] = useState<SystemDependencyStatusResponse | null>(null);
  const [defaultOutputFolder, setDefaultOutputFolder] = useState(() => localStorage.getItem('auto-tool.default-output-folder') || './examples/outputs');
  const [defaultBgmFolder, setDefaultBgmFolder] = useState(() => localStorage.getItem('auto-tool.default-bgm-folder') || '');

  useEffect(() => {
    getAppSettings()
      .then((response) => {
        setSettings(normalizeSettings(response));
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Không thể tải cài đặt chung.'))
      .finally(() => setLoading(false));
    getSystemDependencies().then(setDependencies).catch(() => setDependencies(null));
  }, []);

  function update(patch: Partial<AppSettings>) {
    setSettings((current) => ({ ...current, ...patch }));
    setMessage(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await saveAppSettings(cleanSettings(settings));
      localStorage.setItem('auto-tool.default-output-folder', defaultOutputFolder.trim());
      localStorage.setItem('auto-tool.default-bgm-folder', defaultBgmFolder.trim());
      setSettings(normalizeSettings(saved));
      setMessage('Đã lưu cài đặt chung.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu cài đặt chung.');
    } finally {
      setSaving(false);
    }
  }

  async function handleTestGoogleVoices() {
    setTestingVoices(true);
    setError(null);
    setMessage(null);
    try {
      const response = await getGoogleCloudTTSVoices({
        apiKey: settings.google_tts_api_key,
        credentialsJsonPath: settings.google_tts_credentials_json_path,
        accessToken: settings.google_tts_access_token,
      });
      setMessage(`Google Cloud TTS kết nối thành công. Đã tải ${response.voices.length} giọng.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể kiểm tra Google Cloud TTS.');
    } finally {
      setTestingVoices(false);
    }
  }

  if (loading) {
    return (
      <main className="studio-page">
        <div className="rounded-lg border border-line bg-white p-5 text-sm text-muted shadow-panel">
          Đang tải cài đặt chung...
        </div>
      </main>
    );
  }

  return (
    <main className="studio-page">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-ink">Cài đặt chung</h1>
        <p className="mt-1 text-sm text-muted">
          Các thông tin này chỉ cần nhập một lần và sẽ được backend dùng khi tạo kịch bản hoặc render giọng đọc.
        </p>
      </div>

      <div className="space-y-5">
        <ApiErrorBox error={error} />
        {message ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {message}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <GlassCard className="p-5" strong><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><Cpu size={18} className="text-cyan-200" /><h2 className="font-semibold text-white">Hệ thống xử lý</h2></div><GlassBadge variant={dependencies?.ffmpeg_path ? 'success' : 'warning'}>{dependencies?.ffmpeg_path ? 'Ready' : 'Check setup'}</GlassBadge></div><div className="mt-4 grid gap-2"><Dependency label="FFmpeg" ready={Boolean(dependencies?.ffmpeg_path)} /><Dependency label="ffprobe" ready={Boolean(dependencies?.ffprobe_path)} /><Dependency label={`OCR ${dependencies?.ocr_provider || ''}`} ready={Boolean(dependencies?.ocr_available)} /><Dependency label="Piper TTS" ready={Boolean(dependencies?.piper_path && dependencies?.piper_model_path)} /></div></GlassCard>
          <GlassCard className="p-5" strong><div className="flex items-center gap-2"><Info size={18} className="text-violet-200" /><h2 className="font-semibold text-white">Mặc định workflow</h2></div><div className="mt-4 grid gap-4"><PathInput label="Thư mục output mặc định" value={defaultOutputFolder} onChange={setDefaultOutputFolder} /><PathInput label="Thư mục BGM mặc định" value={defaultBgmFolder} onChange={setDefaultBgmFolder} /></div></GlassCard>
        </div>

        <details className="glass-card-strong p-5">
          <summary className="flex cursor-pointer items-center gap-2 font-semibold text-white"><KeyRound size={17} className="text-amber-200" /> Cấu hình kỹ thuật nâng cao</summary>
          <div className="mt-5 grid gap-5">
          <section className="rounded-md border border-white/10 bg-black/10 p-5">
          <h2 className="mb-3 text-base font-semibold text-ink">Gemini</h2>
          <TextArea
            label="Danh sách Gemini API key"
            value={(settings.gemini_api_keys ?? []).join('\n')}
            rows={6}
            onChange={(value) =>
              update({
                gemini_api_keys: value
                  .split('\n')
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
          <p className="mt-2 text-xs text-muted">
            Mỗi dòng là một key. Khi một key lỗi, backend sẽ xoay sang key tiếp theo.
          </p>
          </section>

        <section className="rounded-md border border-white/10 bg-black/10 p-5">
          <h2 className="mb-3 text-base font-semibold text-ink">Google Cloud TTS</h2>
          <div className="grid gap-4">
            <PathInput
              label="Đường dẫn file Service Account JSON"
              value={settings.google_tts_credentials_json_path ?? ''}
              onChange={(google_tts_credentials_json_path) => update({ google_tts_credentials_json_path })}
              placeholder="D:\\Keys\\google-service-account.json"
              modes={['file']}
              fileExtensions={['.json']}
            />
            <TextInput
              label="API key Google Cloud"
              type="password"
              value={settings.google_tts_api_key ?? ''}
              onChange={(google_tts_api_key) => update({ google_tts_api_key })}
            />
            <TextInput
              label="OAuth access token"
              type="password"
              value={settings.google_tts_access_token ?? ''}
              onChange={(google_tts_access_token) => update({ google_tts_access_token })}
            />
          </div>
          <p className="mt-2 text-xs text-muted">
            Có thể dùng Service Account JSON, OAuth access token hoặc API key Google Cloud tuỳ cách bạn cấu hình tài khoản.
          </p>
        </section>
          </div>
        </details>

        <div className="flex flex-wrap gap-3">
          <button
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300"
            type="button"
            disabled={saving}
            onClick={handleSave}
          >
            {saving ? 'Đang lưu...' : 'Lưu cài đặt'}
          </button>
          <button
            className="rounded-md border border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand disabled:text-muted"
            type="button"
            disabled={testingVoices}
            onClick={handleTestGoogleVoices}
          >
            {testingVoices ? 'Đang kiểm tra...' : 'Kiểm tra Google Cloud TTS'}
          </button>
        </div>
      </div>
    </main>
  );
}

function Dependency({ label, ready }: { label: string; ready: boolean }) {
  return <div className="flex items-center justify-between rounded-md bg-black/15 px-3 py-2 text-sm"><span className="text-slate-300">{label}</span><span className={ready ? 'text-emerald-200' : 'text-amber-200'}><CheckCircle2 size={16} /></span></div>;
}

function normalizeSettings(settings: AppSettings): AppSettings {
  return {
    gemini_api_keys: settings.gemini_api_keys ?? [],
    google_tts_credentials_json_path: settings.google_tts_credentials_json_path ?? '',
    google_tts_api_key: settings.google_tts_api_key ?? '',
    google_tts_access_token: settings.google_tts_access_token ?? '',
    google_tts_favorite_voices: settings.google_tts_favorite_voices ?? [],
    google_tts_preview_text: settings.google_tts_preview_text ?? 'Xin chào, đây là giọng đọc thử của Auto Tool.',
    favorite_music_paths: settings.favorite_music_paths ?? [],
  };
}

function cleanSettings(settings: AppSettings): AppSettings {
  return {
    gemini_api_keys: (settings.gemini_api_keys ?? [])
      .map((item) => item.trim())
      .filter(Boolean),
    google_tts_credentials_json_path: settings.google_tts_credentials_json_path?.trim() || null,
    google_tts_api_key: settings.google_tts_api_key?.trim() || null,
    google_tts_access_token: settings.google_tts_access_token?.trim() || null,
    google_tts_favorite_voices: (settings.google_tts_favorite_voices ?? [])
      .map((item) => item.trim())
      .filter(Boolean),
    google_tts_preview_text: settings.google_tts_preview_text?.trim() || 'Xin chào, đây là giọng đọc thử của Auto Tool.',
    favorite_music_paths: (settings.favorite_music_paths ?? [])
      .map((item) => item.trim())
      .filter(Boolean),
  };
}
