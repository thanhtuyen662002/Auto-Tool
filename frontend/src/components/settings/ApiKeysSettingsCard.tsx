import { useEffect, useState } from 'react';
import { BrainCircuit, CloudLightning, FlaskConical, KeyRound, ShieldCheck } from 'lucide-react';
import { getAppSettings, getGoogleCloudTTSVoices, saveAppSettings } from '../../api/client';
import type { AppSettings } from '../../types/project';
import GlassButton from '../glass/GlassButton';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SettingsSection from './SettingsSection';

const EMPTY: AppSettings = {
  gemini_api_keys: [],
  google_tts_credentials_json_path: '',
  google_tts_api_key: '',
  google_tts_access_token: '',
  google_tts_favorite_voices: [],
  google_tts_preview_text: 'Xin chào, đây là giọng đọc thử của Auto Tool.',
  favorite_music_paths: [],
};

export default function ApiKeysSettingsCard() {
  const [settings, setSettings] = useState<AppSettings>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    getAppSettings()
      .then((res) => setSettings(normalize(res)))
      .catch(() => setMessage({ type: 'error', text: 'Không thể tải cài đặt khóa API.' }))
      .finally(() => setLoading(false));
  }, []);

  function patch(updates: Partial<AppSettings>) {
    setSettings((prev) => ({ ...prev, ...updates }));
    setMessage(null);
  }

  async function handleSave() {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await saveAppSettings(clean(settings));
      setSettings(normalize(saved));
      setMessage({ type: 'success', text: 'Đã lưu cài đặt khóa API.' });
    } catch {
      setMessage({ type: 'error', text: 'Không thể lưu. Kiểm tra lại kết nối bộ xử lý.' });
    } finally {
      setSaving(false);
    }
  }

  async function handleTestGoogleTTS() {
    setTesting(true);
    setMessage(null);
    try {
      const res = await getGoogleCloudTTSVoices({
        apiKey: settings.google_tts_api_key,
        credentialsJsonPath: settings.google_tts_credentials_json_path,
        accessToken: settings.google_tts_access_token,
      });
      setMessage({ type: 'success', text: `Google Cloud TTS kết nối thành công, có ${res.voices.length} giọng.` });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể kết nối Google Cloud TTS.' });
    } finally {
      setTesting(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-lg border border-white/10 bg-black/15 p-5 text-sm text-slate-400">
        Đang tải cài đặt khóa API...
      </div>
    );
  }

  const geminiKeyCount = (settings.gemini_api_keys ?? []).length;

  return (
    <div className="grid gap-5">
      <NotifyOnChange value={message?.text} variant={message?.type ?? 'success'} />

      {/* Status message */}
      {message && (
        <div className={`rounded-md border px-4 py-3 text-sm ${
          message.type === 'success'
            ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
            : 'border-red-400/30 bg-red-400/10 text-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* ── GEMINI ── */}
      <SettingsSection
        title="Gemini AI"
        description="Khóa Gemini dùng để tạo kịch bản, dịch phụ đề và các tính năng AI. Có thể dán nhiều khóa, mỗi dòng một khóa; hệ thống tự đổi khóa khi một khóa hết hạn mức."
      >
        <div className="grid gap-4">
          {/* Key count badge */}
          <div className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3">
            <BrainCircuit size={18} className="shrink-0 text-violet-300" />
            <div className="flex-1 text-sm text-slate-300">
              Đang lưu <span className="font-semibold text-white">{geminiKeyCount}</span> khóa Gemini
            </div>
            {geminiKeyCount > 0 && (
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300">
                <ShieldCheck size={11} className="mr-1 inline" />Đang hoạt động
              </span>
            )}
          </div>

          {/* Textarea */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-slate-400">
              Danh sách khóa Gemini (mỗi dòng một khóa)
            </label>
            <textarea
              id="gemini-api-keys"
              className="min-h-40 w-full resize-y whitespace-pre-wrap rounded-md border border-white/10 bg-black/20 px-3 py-2.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-violet-400/60 focus:outline-none focus:ring-1 focus:ring-violet-400/30"
              rows={6}
              placeholder={'AIzaSy... (khóa 1)\nAIzaSy... (khóa 2)'}
              autoCapitalize="off"
              autoComplete="off"
              spellCheck={false}
              value={(settings.gemini_api_keys ?? []).join('\n')}
              onChange={(e) =>
                patch({
                  gemini_api_keys: e.target.value
                    .split('\n')
                    .map((k) => k.trim())
                    .filter(Boolean),
                })
              }
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Lấy key tại{' '}
              <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer" className="text-violet-400 underline hover:text-violet-300">
                aistudio.google.com/apikey
              </a>
              . Khi một khóa vượt hạn mức, hệ thống tự chuyển sang khóa tiếp theo.
            </p>
          </div>
        </div>
      </SettingsSection>

      {/* ── GOOGLE CLOUD TTS ── */}
      <SettingsSection
        title="Google Cloud TTS"
        description="Dùng để tạo giọng đọc tiếng Việt chất lượng cao. Chỉ cần cấu hình nếu bạn chọn Google Cloud TTS trong dự án."
      >
        <div className="grid gap-4">
          {/* Auth method info */}
          <div className="rounded-md border border-amber-400/20 bg-amber-400/8 px-4 py-3 text-xs text-amber-200">
            <strong>Chọn một trong ba cách xác thực:</strong> Service Account JSON (khuyến nghị cho production),
            OAuth Access Token (tạm thời), hoặc API Key (giới hạn tính năng).
          </div>

          {/* Service Account JSON Path */}
          <div>
            <label htmlFor="gcp-sa-json" className="mb-1.5 block text-xs font-medium text-slate-400">
              <CloudLightning size={12} className="mr-1 inline text-cyan-300" />
              Đường dẫn file Service Account JSON <span className="text-emerald-400">(khuyến nghị)</span>
            </label>
            <input
              id="gcp-sa-json"
              type="text"
              className="w-full rounded-md border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-cyan-400/60 focus:outline-none focus:ring-1 focus:ring-cyan-400/30"
              placeholder="D:\Keys\google-service-account.json"
              value={settings.google_tts_credentials_json_path ?? ''}
              onChange={(e) => patch({ google_tts_credentials_json_path: e.target.value })}
            />
            <p className="mt-1 text-xs text-slate-500">
              Tạo Service Account trong{' '}
              <a href="https://console.cloud.google.com/iam-admin/serviceaccounts" target="_blank" rel="noreferrer" className="text-cyan-400 underline hover:text-cyan-300">
                Google Cloud Console
              </a>{' '}
              → tải JSON key.
            </p>
          </div>

          {/* API Key */}
          <div>
            <label htmlFor="gcp-api-key" className="mb-1.5 block text-xs font-medium text-slate-400">
              <KeyRound size={12} className="mr-1 inline text-amber-300" />
              Khóa API Google Cloud
            </label>
            <input
              id="gcp-api-key"
              type="password"
              className="w-full rounded-md border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/30"
              placeholder="AIzaSy..."
              autoComplete="new-password"
              value={settings.google_tts_api_key ?? ''}
              onChange={(e) => patch({ google_tts_api_key: e.target.value })}
            />
          </div>

          {/* OAuth Access Token */}
          <div>
            <label htmlFor="gcp-access-token" className="mb-1.5 block text-xs font-medium text-slate-400">
              OAuth Access Token <span className="text-slate-500">(tạm thời, hết hạn sau 1 giờ)</span>
            </label>
            <input
              id="gcp-access-token"
              type="password"
              className="w-full rounded-md border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs text-slate-200 placeholder-slate-600 focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/10"
              placeholder="ya29...."
              autoComplete="new-password"
              value={settings.google_tts_access_token ?? ''}
              onChange={(e) => patch({ google_tts_access_token: e.target.value })}
            />
          </div>

          {/* Test button */}
          <div>
            <GlassButton variant="ghost" loading={testing} onClick={() => void handleTestGoogleTTS()}>
              <FlaskConical size={14} />
              Kiểm tra kết nối Google Cloud TTS
            </GlassButton>
          </div>
        </div>
      </SettingsSection>

      {/* Save */}
      <div className="flex flex-wrap gap-3">
        <GlassButton variant="primary" loading={saving} onClick={() => void handleSave()}>
          <ShieldCheck size={15} />
          Lưu khóa API
        </GlassButton>
      </div>
    </div>
  );
}

function normalize(s: AppSettings): AppSettings {
  return {
    gemini_api_keys: s.gemini_api_keys ?? [],
    google_tts_credentials_json_path: s.google_tts_credentials_json_path ?? '',
    google_tts_api_key: s.google_tts_api_key ?? '',
    google_tts_access_token: s.google_tts_access_token ?? '',
    google_tts_favorite_voices: s.google_tts_favorite_voices ?? [],
    google_tts_preview_text: s.google_tts_preview_text ?? 'Xin chào, đây là giọng đọc thử của Auto Tool.',
    favorite_music_paths: s.favorite_music_paths ?? [],
  };
}

function clean(s: AppSettings): AppSettings {
  return {
    gemini_api_keys: (s.gemini_api_keys ?? []).map((k) => k.trim()).filter(Boolean),
    google_tts_credentials_json_path: s.google_tts_credentials_json_path?.trim() || null,
    google_tts_api_key: s.google_tts_api_key?.trim() || null,
    google_tts_access_token: s.google_tts_access_token?.trim() || null,
    google_tts_favorite_voices: (s.google_tts_favorite_voices ?? []).map((voice) => voice.trim()).filter(Boolean),
    google_tts_preview_text: s.google_tts_preview_text?.trim() || 'Xin chào, đây là giọng đọc thử của Auto Tool.',
    favorite_music_paths: (s.favorite_music_paths ?? []).map((path) => path.trim()).filter(Boolean),
  };
}
