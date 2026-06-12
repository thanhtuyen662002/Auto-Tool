import { useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassInput from '../glass/GlassInput';
import SettingsSection from './SettingsSection';
import { clearRecentFolders, getLocalUiSettings, readRecentFolders, recentFolderKeys, saveLocalUiSettings } from '../../utils/localSettings';

export default function PathSettingsCard({ onSaved }: { onSaved?: () => void }) {
  const initial = useMemo(() => getLocalUiSettings(), []);
  const [defaultOutputFolder, setDefaultOutputFolder] = useState(initial.defaultOutputFolder);
  const [defaultMusicFolder, setDefaultMusicFolder] = useState(initial.defaultMusicFolder);
  const [defaultSourceFolder, setDefaultSourceFolder] = useState(initial.defaultSourceFolder);
  const [message, setMessage] = useState<string | null>(null);
  const recentFolders = [
    ...readRecentFolders(recentFolderKeys.source),
    ...readRecentFolders(recentFolderKeys.output),
    ...readRecentFolders(recentFolderKeys.music),
  ];

  function save() {
    saveLocalUiSettings({ defaultOutputFolder, defaultMusicFolder, defaultSourceFolder });
    setMessage('Đã lưu path mặc định.');
    onSaved?.();
  }

  function clearRecent() {
    clearRecentFolders();
    setMessage('Đã xóa recent folders.');
  }

  return (
    <SettingsSection title="Paths" description="Các đường dẫn này chỉ lưu trên máy của bạn, không chứa API key hoặc thông tin nhạy cảm.">
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassInput label="Default output folder" value={defaultOutputFolder} onChange={(event) => setDefaultOutputFolder(event.target.value)} placeholder="D:/auto-tool/outputs" />
        <GlassInput label="Default music folder" value={defaultMusicFolder} onChange={(event) => setDefaultMusicFolder(event.target.value)} placeholder="D:/music" />
        <GlassInput label="Default source folder optional" value={defaultSourceFolder} onChange={(event) => setDefaultSourceFolder(event.target.value)} placeholder="D:/douyin/videos" />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="primary" onClick={save}>Save</GlassButton>
        <GlassButton variant="secondary" onClick={() => setDefaultOutputFolder('./examples/outputs')}>Use default</GlassButton>
        <GlassButton variant="ghost" onClick={clearRecent}>Clear recent folders</GlassButton>
      </div>
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
      <div className="mt-5 rounded-md border border-white/10 bg-black/15 p-4">
        <div className="text-sm font-semibold text-white">Recent folders</div>
        {recentFolders.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {[...new Set(recentFolders)].slice(0, 8).map((folder) => (
              <span className="max-w-full truncate rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs text-slate-300" key={folder}>{folder}</span>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Chưa có recent folders.</p>
        )}
      </div>
    </SettingsSection>
  );
}
