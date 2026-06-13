import type { ReactNode } from 'react';
import GlassTabs from '../glass/GlassTabs';

export type SettingsTab = 'general' | 'paths' | 'local_app' | 'data_management' | 'providers' | 'appearance' | 'advanced' | 'about';

const tabs: Array<{ value: SettingsTab; label: string }> = [
  { value: 'general', label: 'General' },
  { value: 'paths', label: 'Paths' },
  { value: 'local_app', label: 'Local App' },
  { value: 'data_management', label: 'Dữ liệu' },
  { value: 'providers', label: 'Providers' },
  { value: 'appearance', label: 'Appearance' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'about', label: 'About' },
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
