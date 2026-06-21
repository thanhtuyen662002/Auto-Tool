import { useEffect, useMemo, useRef, useState } from 'react';
import { FolderOpen, Music2, PlayCircle, RefreshCw, Save, Search, Star, Volume2 } from 'lucide-react';
import {
  audioFileUrl,
  browsePath,
  getAppSettings,
  getGoogleCloudTTSVoices,
  getMusicLibrary,
  previewTTSVoice,
  saveAppSettings,
} from '../../api/client';
import { getLocalAppConfig } from '../../services/localAppApi';
import type { AppSettings, MusicLibraryTrack, TTSVoiceInfo } from '../../types/project';
import GlassButton from '../glass/GlassButton';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SettingsSection from './SettingsSection';

const DEFAULT_PREVIEW_TEXT = 'Xin chào, đây là giọng đọc thử của Auto Tool.';

const EMPTY_SETTINGS: AppSettings = {
  gemini_api_keys: [],
  google_tts_credentials_json_path: '',
  google_tts_api_key: '',
  google_tts_access_token: '',
  google_tts_favorite_voices: [],
  google_tts_preview_text: DEFAULT_PREVIEW_TEXT,
  favorite_music_paths: [],
};

export default function VoiceMusicLibrarySettingsCard() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [settings, setSettings] = useState<AppSettings>(EMPTY_SETTINGS);
  const [languageCode, setLanguageCode] = useState('vi-VN');
  const [voices, setVoices] = useState<TTSVoiceInfo[]>([]);
  const [voiceSearch, setVoiceSearch] = useState('');
  const [musicFolder, setMusicFolder] = useState('');
  const [tracks, setTracks] = useState<MusicLibraryTrack[]>([]);
  const [musicSearch, setMusicSearch] = useState('');
  const [audioSrc, setAudioSrc] = useState('');
  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null);
  const [loadingVoices, setLoadingVoices] = useState(false);
  const [loadingMusic, setLoadingMusic] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      getAppSettings().catch(() => EMPTY_SETTINGS),
      getLocalAppConfig().catch(() => null),
    ]).then(([appSettings, localConfig]) => {
      if (!mounted) return;
      const normalized = normalizeSettings(appSettings);
      setSettings(normalized);
      setMusicFolder(localConfig?.default_music_folder || 'examples/music');
      void loadVoices(normalized, languageCode);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const favoriteVoiceSet = useMemo(
    () => new Set((settings.google_tts_favorite_voices ?? []).map((voice) => voice.trim()).filter(Boolean)),
    [settings.google_tts_favorite_voices],
  );
  const favoriteMusicSet = useMemo(
    () => new Set((settings.favorite_music_paths ?? []).map((path) => path.trim()).filter(Boolean)),
    [settings.favorite_music_paths],
  );

  const visibleVoices = useMemo(() => {
    const query = voiceSearch.trim().toLowerCase();
    return [...voices]
      .filter((voice) => {
        if (!query) return true;
        return (
          voice.name.toLowerCase().includes(query) ||
          voice.ssml_gender.toLowerCase().includes(query) ||
          voice.language_codes.some((code) => code.toLowerCase().includes(query))
        );
      })
      .sort((a, b) => Number(favoriteVoiceSet.has(b.name)) - Number(favoriteVoiceSet.has(a.name)) || a.name.localeCompare(b.name));
  }, [favoriteVoiceSet, voiceSearch, voices]);

  const visibleTracks = useMemo(() => {
    const query = musicSearch.trim().toLowerCase();
    return [...tracks]
      .filter((track) => !query || track.filename.toLowerCase().includes(query) || track.path.toLowerCase().includes(query))
      .sort((a, b) => Number(b.favorite) - Number(a.favorite) || a.filename.localeCompare(b.filename));
  }, [musicSearch, tracks]);

  async function loadVoices(sourceSettings = settings, nextLanguageCode = languageCode) {
    setLoadingVoices(true);
    setMessage(null);
    try {
      const response = await getGoogleCloudTTSVoices(
        {
          apiKey: sourceSettings.google_tts_api_key,
          credentialsJsonPath: sourceSettings.google_tts_credentials_json_path,
          accessToken: sourceSettings.google_tts_access_token,
        },
        nextLanguageCode,
      );
      setVoices(response.voices);
      setMessage({ type: 'success', text: `Đã tải ${response.voices.length} giọng Google Cloud TTS.` });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể tải danh sách giọng Google Cloud TTS.' });
    } finally {
      setLoadingVoices(false);
    }
  }

  async function loadMusic(folder = musicFolder) {
    setLoadingMusic(true);
    setMessage(null);
    try {
      const response = await getMusicLibrary(folder.trim() || null);
      setTracks(response.tracks);
      setMessage({ type: 'success', text: `Đã quét ${response.tracks.length} file nhạc.` });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể quét thư mục nhạc.' });
    } finally {
      setLoadingMusic(false);
    }
  }

  async function chooseMusicFolder() {
    try {
      const response = await browsePath({
        mode: 'folder',
        title: 'Chọn thư mục nhạc nền',
        initial_path: musicFolder || undefined,
        extensions: [],
      });
      if (response.path) {
        setMusicFolder(response.path);
        await loadMusic(response.path);
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể mở hộp chọn thư mục.' });
    }
  }

  async function toggleVoice(voiceName: string) {
    const current = settings.google_tts_favorite_voices ?? [];
    const next = favoriteVoiceSet.has(voiceName)
      ? current.filter((item) => item !== voiceName)
      : [...current, voiceName];
    await persistSettings({ google_tts_favorite_voices: next }, 'Đã cập nhật danh sách giọng yêu thích.');
  }

  async function toggleTrack(track: MusicLibraryTrack) {
    const current = settings.favorite_music_paths ?? [];
    const next = favoriteMusicSet.has(track.path)
      ? current.filter((item) => item !== track.path)
      : [...current, track.path];
    await persistSettings({ favorite_music_paths: next }, 'Đã cập nhật danh sách nhạc ưu tiên.');
    setTracks((items) => items.map((item) => (item.path === track.path ? { ...item, favorite: !track.favorite } : item)));
  }

  async function updatePreviewText(value: string) {
    setSettings((current) => ({ ...current, google_tts_preview_text: value }));
  }

  async function savePreviewText() {
    await persistSettings(
      { google_tts_preview_text: settings.google_tts_preview_text || DEFAULT_PREVIEW_TEXT },
      'Đã lưu câu nghe thử.',
    );
  }

  async function previewVoice(voiceName: string) {
    setPreviewingVoice(voiceName);
    setMessage(null);
    try {
      const response = await previewTTSVoice({
        provider: 'google_cloud_tts',
        voice: voiceName,
        text: settings.google_tts_preview_text || DEFAULT_PREVIEW_TEXT,
        language: 'vi',
        apiKey: settings.google_tts_api_key,
        credentialsJsonPath: settings.google_tts_credentials_json_path,
        accessToken: settings.google_tts_access_token,
      });
      setAudioSrc(audioFileUrl(response.path));
      setTimeout(() => {
        void audioRef.current?.play().catch(() => undefined);
      }, 50);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể tạo file nghe thử.' });
    } finally {
      setPreviewingVoice(null);
    }
  }

  async function persistSettings(patch: Partial<AppSettings>, successText: string) {
    setSaving(true);
    setMessage(null);
    try {
      const next = cleanSettings({ ...settings, ...patch });
      const saved = await saveAppSettings(next);
      setSettings(normalizeSettings(saved));
      setMessage({ type: 'success', text: successText });
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Không thể lưu cài đặt.' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-5">
      <NotifyOnChange value={message?.text} variant={message?.type ?? 'success'} />

      {message ? (
        <div
          className={`rounded-md border px-4 py-3 text-sm ${
            message.type === 'error'
              ? 'border-rose-400/30 bg-rose-400/10 text-rose-200'
              : message.type === 'success'
                ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                : 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100'
          }`}
        >
          {message.text}
        </div>
      ) : null}

      <SettingsSection
        title="Thư viện giọng Google Cloud TTS"
        description="Tải toàn bộ giọng Google trả về, nghe thử, rồi đánh dấu sao. Khi render, Auto Tool sẽ chọn một giọng trong danh sách đã đánh dấu."
      >
        <div className="grid gap-4">
          <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)_auto]">
            <label className="grid gap-1 text-sm text-slate-300">
              Mã ngôn ngữ
              <input
                className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
                value={languageCode}
                onChange={(event) => setLanguageCode(event.target.value)}
              />
            </label>
            <label className="grid gap-1 text-sm text-slate-300">
              Tìm giọng
              <span className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
                <input
                  className="w-full rounded-md border border-white/10 bg-black/20 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-cyan-300/60"
                  placeholder="Nhập tên giọng, giới tính hoặc mã ngôn ngữ"
                  value={voiceSearch}
                  onChange={(event) => setVoiceSearch(event.target.value)}
                />
              </span>
            </label>
            <div className="flex items-end">
              <GlassButton variant="secondary" loading={loadingVoices} onClick={() => void loadVoices(settings, languageCode)}>
                <RefreshCw size={15} />
                Tải danh sách
              </GlassButton>
            </div>
          </div>

          <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_auto]">
            <input
              className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
              value={settings.google_tts_preview_text ?? DEFAULT_PREVIEW_TEXT}
              onChange={(event) => void updatePreviewText(event.target.value)}
            />
            <GlassButton variant="ghost" loading={saving} onClick={() => void savePreviewText()}>
              <Save size={15} />
              Lưu câu thử
            </GlassButton>
          </div>

          <audio ref={audioRef} className="w-full" controls src={audioSrc || undefined} />

          <div className="grid gap-2">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">
              Đã đánh dấu {favoriteVoiceSet.size} giọng
            </div>
            <div className="grid max-h-[420px] gap-2 overflow-y-auto pr-1">
              {visibleVoices.map((voice) => (
                <VoiceRow
                  key={voice.name}
                  favorite={favoriteVoiceSet.has(voice.name)}
                  previewing={previewingVoice === voice.name}
                  saving={saving}
                  voice={voice}
                  onPreview={() => void previewVoice(voice.name)}
                  onToggle={() => void toggleVoice(voice.name)}
                />
              ))}
              {!visibleVoices.length ? (
                <div className="rounded-md border border-white/10 bg-black/15 p-4 text-sm text-slate-400">
                  Chưa có giọng nào. Bấm “Tải danh sách” sau khi cấu hình Google Cloud TTS.
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Thư viện nhạc nền"
        description="Quét thư mục nhạc, đánh dấu sao các bài muốn ưu tiên. Render sẽ chọn nhạc trong danh sách ưu tiên trước, nếu chưa có thì mới chọn ngẫu nhiên trong folder."
      >
        <div className="grid gap-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
            <label className="grid gap-1 text-sm text-slate-300">
              Thư mục nhạc
              <input
                className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60"
                value={musicFolder}
                onChange={(event) => setMusicFolder(event.target.value)}
              />
            </label>
            <div className="flex items-end">
              <GlassButton variant="secondary" onClick={() => void chooseMusicFolder()}>
                <FolderOpen size={15} />
                Chọn thư mục
              </GlassButton>
            </div>
            <div className="flex items-end">
              <GlassButton variant="primary" loading={loadingMusic} onClick={() => void loadMusic()}>
                <RefreshCw size={15} />
                Quét nhạc
              </GlassButton>
            </div>
          </div>

          <label className="grid gap-1 text-sm text-slate-300">
            Tìm bài nhạc
            <span className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input
                className="w-full rounded-md border border-white/10 bg-black/20 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-cyan-300/60"
                placeholder="Nhập tên file hoặc đường dẫn"
                value={musicSearch}
                onChange={(event) => setMusicSearch(event.target.value)}
              />
            </span>
          </label>

          <div className="text-xs uppercase tracking-[0.24em] text-slate-500">
            Đã đánh dấu {favoriteMusicSet.size} bài nhạc
          </div>
          <div className="grid max-h-[420px] gap-2 overflow-y-auto pr-1">
            {visibleTracks.map((track) => (
              <MusicRow
                key={track.path}
                favorite={favoriteMusicSet.has(track.path)}
                saving={saving}
                track={track}
                onToggle={() => void toggleTrack(track)}
              />
            ))}
            {!visibleTracks.length ? (
              <div className="rounded-md border border-white/10 bg-black/15 p-4 text-sm text-slate-400">
                Chưa có bài nhạc nào. Chọn thư mục rồi bấm “Quét nhạc”.
              </div>
            ) : null}
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}

function VoiceRow({
  favorite,
  previewing,
  saving,
  voice,
  onPreview,
  onToggle,
}: {
  favorite: boolean;
  previewing: boolean;
  saving: boolean;
  voice: TTSVoiceInfo;
  onPreview: () => void;
  onToggle: () => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-white/10 bg-black/15 p-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-white">{voice.name}</div>
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-400">
          <span>{voice.language_codes.join(', ') || 'Không rõ ngôn ngữ'}</span>
          <span>{voice.ssml_gender || 'Không rõ giới tính'}</span>
          <span>{voice.natural_sample_rate_hertz ? `${voice.natural_sample_rate_hertz.toLocaleString('vi-VN')} Hz` : 'Không rõ Hz'}</span>
        </div>
      </div>
      <GlassButton variant="ghost" loading={previewing} onClick={onPreview}>
        <PlayCircle size={15} />
        Nghe thử
      </GlassButton>
      <GlassButton variant={favorite ? 'primary' : 'secondary'} disabled={saving} onClick={onToggle}>
        <Star size={15} fill={favorite ? 'currentColor' : 'none'} />
        {favorite ? 'Đã sao' : 'Đánh sao'}
      </GlassButton>
    </div>
  );
}

function MusicRow({
  favorite,
  saving,
  track,
  onToggle,
}: {
  favorite: boolean;
  saving: boolean;
  track: MusicLibraryTrack;
  onToggle: () => void;
}) {
  return (
    <div className="grid gap-3 rounded-md border border-white/10 bg-black/15 p-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <Music2 size={16} className="shrink-0 text-cyan-200" />
          <div className="truncate text-sm font-semibold text-white">{track.filename}</div>
        </div>
        <div className="mt-1 truncate text-xs text-slate-500">{track.path}</div>
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-400">
          <span>{formatBytes(track.size_bytes)}</span>
          <span>{track.duration ? formatDuration(track.duration) : 'Chưa đọc duration'}</span>
        </div>
      </div>
      <GlassButton variant={favorite ? 'primary' : 'secondary'} disabled={saving} onClick={onToggle}>
        <Star size={15} fill={favorite ? 'currentColor' : 'none'} />
        {favorite ? 'Ưu tiên' : 'Đánh sao'}
      </GlassButton>
    </div>
  );
}

function normalizeSettings(settings: AppSettings): AppSettings {
  return {
    gemini_api_keys: settings.gemini_api_keys ?? [],
    google_tts_credentials_json_path: settings.google_tts_credentials_json_path ?? '',
    google_tts_api_key: settings.google_tts_api_key ?? '',
    google_tts_access_token: settings.google_tts_access_token ?? '',
    google_tts_favorite_voices: settings.google_tts_favorite_voices ?? [],
    google_tts_preview_text: settings.google_tts_preview_text ?? DEFAULT_PREVIEW_TEXT,
    favorite_music_paths: settings.favorite_music_paths ?? [],
  };
}

function cleanSettings(settings: AppSettings): AppSettings {
  return {
    gemini_api_keys: (settings.gemini_api_keys ?? []).map((item) => item.trim()).filter(Boolean),
    google_tts_credentials_json_path: settings.google_tts_credentials_json_path?.trim() || null,
    google_tts_api_key: settings.google_tts_api_key?.trim() || null,
    google_tts_access_token: settings.google_tts_access_token?.trim() || null,
    google_tts_favorite_voices: (settings.google_tts_favorite_voices ?? []).map((item) => item.trim()).filter(Boolean),
    google_tts_preview_text: settings.google_tts_preview_text?.trim() || DEFAULT_PREVIEW_TEXT,
    favorite_music_paths: (settings.favorite_music_paths ?? []).map((item) => item.trim()).filter(Boolean),
  };
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDuration(value: number): string {
  const total = Math.max(0, Math.round(value));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
