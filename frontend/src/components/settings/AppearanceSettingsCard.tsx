import { useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassSelect from '../glass/GlassSelect';
import SettingsSection from './SettingsSection';
import { applyAppearanceSettings, getLocalUiSettings, saveLocalUiSettings, type GlassIntensity, type LayoutDensity } from '../../utils/localSettings';

export default function AppearanceSettingsCard() {
  const initial = useMemo(() => getLocalUiSettings(), []);
  const [glassIntensity, setGlassIntensity] = useState<GlassIntensity>(initial.glassIntensity);
  const [reduceMotion, setReduceMotion] = useState(initial.reduceMotion);
  const [layoutDensity, setLayoutDensity] = useState<LayoutDensity>(initial.layoutDensity);
  const [message, setMessage] = useState<string | null>(null);

  function save() {
    const next = { glassIntensity, reduceMotion, layoutDensity };
    saveLocalUiSettings(next);
    applyAppearanceSettings({ ...getLocalUiSettings(), ...next });
    setMessage('Đã áp dụng giao diện.');
  }

  return (
    <SettingsSection title="Giao diện & Chủ đề" description="Tinh chỉnh giao diện hiệu ứng kính (Glassmorphism) cục bộ của ứng dụng.">
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassSelect label="Chủ đề mặc định" value="dark-glass" disabled>
          <option value="dark-glass">Dark Glass (Mặc định)</option>
        </GlassSelect>
        <GlassSelect label="Độ đậm kính mờ" value={glassIntensity} onChange={(event) => setGlassIntensity(event.target.value as GlassIntensity)}>
          <option value="soft">Nhẹ nhàng</option>
          <option value="medium">Vừa phải</option>
          <option value="strong">Đậm nét</option>
        </GlassSelect>
        <GlassSelect label="Mật độ bố cục" value={layoutDensity} onChange={(event) => setLayoutDensity(event.target.value as LayoutDensity)}>
          <option value="comfortable">Dễ nhìn</option>
          <option value="compact">Gọn gàng</option>
        </GlassSelect>
      </div>
      <label className="mt-4 flex items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
        <input type="checkbox" checked={reduceMotion} onChange={(event) => setReduceMotion(event.target.checked)} />
        Giảm chuyển động cho các hiệu ứng động chính
      </label>
      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="primary" onClick={save} className="hover:scale-[1.02] active:scale-[0.98] transition-all">Áp dụng</GlassButton>
      </div>
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
    </SettingsSection>
  );
}
