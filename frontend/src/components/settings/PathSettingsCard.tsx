import { useEffect, useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import PathInput from '../PathInput';
import SettingsSection from './SettingsSection';
import {
  DEFAULT_LOCAL_APP_CONFIG,
  getLocalAppConfig,
  saveLocalAppConfig,
  type LocalAppConfig,
} from '../../services/localAppApi';
import {
  clearRecentFolders,
  getLocalUiSettings,
  readRecentFolders,
  recentFolderKeys,
  saveLocalUiSettings,
} from '../../utils/localSettings';

export default function PathSettingsCard({ onSaved }: { onSaved?: () => void }) {
  const initial = useMemo(() => getLocalUiSettings(), []);
  const [defaultOutputFolder, setDefaultOutputFolder] = useState(initial.defaultOutputFolder);
  const [defaultMusicFolder, setDefaultMusicFolder] = useState(initial.defaultMusicFolder);
  const [defaultSourceFolder, setDefaultSourceFolder] = useState(initial.defaultSourceFolder);
  const [localAppConfig, setLocalAppConfig] = useState<LocalAppConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const recentFolders = [
    ...readRecentFolders(recentFolderKeys.source),
    ...readRecentFolders(recentFolderKeys.output),
    ...readRecentFolders(recentFolderKeys.music),
  ];

  useEffect(() => {
    getLocalAppConfig()
      .then((config) => {
        setLocalAppConfig(config);
        setDefaultOutputFolder(config.default_output_folder || initial.defaultOutputFolder);
        setDefaultMusicFolder(config.default_music_folder || initial.defaultMusicFolder);
        setDefaultSourceFolder(config.default_source_folder || initial.defaultSourceFolder);
      })
      .catch(() => undefined);
  }, [initial.defaultMusicFolder, initial.defaultOutputFolder, initial.defaultSourceFolder]);

  async function save() {
    setSaving(true);
    setMessage(null);
    saveLocalUiSettings({ defaultOutputFolder, defaultMusicFolder, defaultSourceFolder });
    try {
      const saved = await saveLocalAppConfig({
        ...(localAppConfig ?? DEFAULT_LOCAL_APP_CONFIG),
        default_output_folder: defaultOutputFolder,
        default_music_folder: defaultMusicFolder,
        default_source_folder: defaultSourceFolder,
      });
      setLocalAppConfig(saved);
      setMessage('Đã lưu thư mục mặc định.');
      onSaved?.();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không thể lưu thư mục mặc định.');
    } finally {
      setSaving(false);
    }
  }

  function clearRecent() {
    clearRecentFolders();
    setMessage('Đã xóa danh sách thư mục gần đây.');
  }

  return (
    <SettingsSection
      title="Thư mục & đường dẫn"
      description="Các đường dẫn này được lưu trên máy của bạn và sẽ tự điền vào các lần tạo dự án tiếp theo."
    >
      <div className="grid gap-4 lg:grid-cols-3">
        <PathInput
          label="Thư mục đầu ra mặc định"
          value={defaultOutputFolder}
          onChange={setDefaultOutputFolder}
          placeholder="D:/auto-tool/outputs"
        />
        <PathInput
          label="Thư mục nhạc mặc định"
          value={defaultMusicFolder}
          onChange={setDefaultMusicFolder}
          placeholder="D:/music"
        />
        <PathInput
          label="Thư mục nguồn mặc định"
          value={defaultSourceFolder}
          onChange={setDefaultSourceFolder}
          placeholder="D:/douyin/videos"
        />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="primary" onClick={() => void save()} disabled={saving}>
          {saving ? 'Đang lưu...' : 'Lưu cấu hình'}
        </GlassButton>
        <GlassButton variant="secondary" onClick={() => setDefaultOutputFolder('./examples/outputs')}>
          Dùng mặc định
        </GlassButton>
        <GlassButton variant="ghost" onClick={clearRecent}>
          Xóa danh sách thư mục gần đây
        </GlassButton>
      </div>
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
      <div className="mt-5 rounded-md border border-white/10 bg-black/15 p-4">
        <div className="text-sm font-semibold text-white">Các thư mục đã mở gần đây</div>
        {recentFolders.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {[...new Set(recentFolders)].slice(0, 8).map((folder) => (
              <span
                className="max-w-full truncate rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs text-slate-300"
                key={folder}
              >
                {folder}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Chưa có thư mục gần đây.</p>
        )}
      </div>
    </SettingsSection>
  );
}
