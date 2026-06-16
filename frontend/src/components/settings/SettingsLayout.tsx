import type { ReactNode } from 'react';
import GlassTabs from '../glass/GlassTabs';

export type SettingsTab =
  | 'general'
  | 'api_keys'
  | 'voice_music'
  | 'paths'
  | 'local_app'
  | 'data_management'
  | 'providers'
  | 'appearance'
  | 'advanced'
  | 'about';

const tabs: Array<{ value: SettingsTab; label: string }> = [
  { value: 'general', label: 'Cấu hình chung' },
  { value: 'api_keys', label: 'Khóa API' },
  { value: 'voice_music', label: 'Giọng & Nhạc' },
  { value: 'paths', label: 'Thư mục & Đường dẫn' },
  { value: 'local_app', label: 'Ứng dụng Local' },
  { value: 'data_management', label: 'Quản lý dữ liệu' },
  { value: 'providers', label: 'Dịch thuật & TTS' },
  { value: 'appearance', label: 'Giao diện & Theme' },
  { value: 'advanced', label: 'Cấu hình nâng cao' },
  { value: 'about', label: 'Giới thiệu' },
];

export default function SettingsLayout({
  activeTab,
  onTabChange,
  children,
}: {
  activeTab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-5">
      <div className="overflow-x-auto pb-1">
        <GlassTabs items={tabs} value={activeTab} onChange={onTabChange} />
      </div>
      {children}
    </div>
  );
}
