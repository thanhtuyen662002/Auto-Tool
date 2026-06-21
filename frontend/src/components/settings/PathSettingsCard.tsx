import { useEffect, useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import { notificationVariantFromText } from '../notifications/NotificationProvider';
import NotifyOnChange from '../notifications/NotifyOnChange';
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

const DEFAULT_OUTPUT_FOLDER = './examples/outputs';

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
        const merged = mergeFolderDefaults(config, getLocalUiSettings());
        setLocalAppConfig({ ...config, ...merged });
        setDefaultOutputFolder(merged.default_output_folder);
        setDefaultMusicFolder(merged.default_music_folder);
        setDefaultSourceFolder(merged.default_source_folder);
      })
      .catch(() => undefined);
  }, []);

  async function save() {
    setSaving(true);
    setMessage(null);
    const folderDefaults = {
      default_source_folder: defaultSourceFolder.trim(),
      default_output_folder: defaultOutputFolder.trim() || DEFAULT_OUTPUT_FOLDER,
      default_music_folder: defaultMusicFolder.trim(),
    };
    saveLocalUiSettings({
      defaultOutputFolder: folderDefaults.default_output_folder,
      defaultMusicFolder: folderDefaults.default_music_folder,
      defaultSourceFolder: folderDefaults.default_source_folder,
    });
    try {
      const saved = await saveLocalAppConfig({
        ...(localAppConfig ?? DEFAULT_LOCAL_APP_CONFIG),
        ...folderDefaults,
      });
      const merged = mergeFolderDefaults(saved, getLocalUiSettings());
      setLocalAppConfig({ ...saved, ...merged });
      setDefaultOutputFolder(merged.default_output_folder);
      setDefaultMusicFolder(merged.default_music_folder);
      setDefaultSourceFolder(merged.default_source_folder);
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
      description="Các đường dẫn này được lưu trong hồ sơ local của Auto Tool và sẽ tự điền vào các lần tạo dự án tiếp theo."
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
        <GlassButton variant="secondary" onClick={() => setDefaultOutputFolder(DEFAULT_OUTPUT_FOLDER)}>
          Dùng mặc định
        </GlassButton>
        <GlassButton variant="ghost" onClick={clearRecent}>
          Xóa danh sách thư mục gần đây
        </GlassButton>
      </div>
      <NotifyOnChange value={message} variant={notificationVariantFromText(message)} />
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

function mergeFolderDefaults(
  config: LocalAppConfig,
  local: ReturnType<typeof getLocalUiSettings>,
): Pick<LocalAppConfig, 'default_output_folder' | 'default_music_folder' | 'default_source_folder'> {
  const backendOutput = config.default_output_folder?.trim() || '';
  const localOutput = local.defaultOutputFolder?.trim() || '';
  return {
    default_output_folder:
      backendOutput && !(backendOutput === DEFAULT_OUTPUT_FOLDER && localOutput && localOutput !== DEFAULT_OUTPUT_FOLDER)
        ? backendOutput
        : localOutput || DEFAULT_OUTPUT_FOLDER,
    default_music_folder: config.default_music_folder?.trim() || local.defaultMusicFolder || '',
    default_source_folder: config.default_source_folder?.trim() || local.defaultSourceFolder || '',
  };
}
