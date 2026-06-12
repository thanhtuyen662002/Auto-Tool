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
    <SettingsSection title="Appearance" description="Tinh chỉnh nhẹ giao diện glass mà không đổi theme phức tạp.">
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassSelect label="Theme" value="dark-glass" disabled>
          <option value="dark-glass">Dark Glass</option>
        </GlassSelect>
        <GlassSelect label="Glass intensity" value={glassIntensity} onChange={(event) => setGlassIntensity(event.target.value as GlassIntensity)}>
          <option value="soft">Soft</option>
          <option value="medium">Medium</option>
          <option value="strong">Strong</option>
        </GlassSelect>
        <GlassSelect label="Layout density" value={layoutDensity} onChange={(event) => setLayoutDensity(event.target.value as LayoutDensity)}>
          <option value="comfortable">Comfortable</option>
          <option value="compact">Compact</option>
        </GlassSelect>
      </div>
      <label className="mt-4 flex items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
        <input type="checkbox" checked={reduceMotion} onChange={(event) => setReduceMotion(event.target.checked)} />
        Reduce motion cho animation chính
      </label>
      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="primary" onClick={save}>Áp dụng</GlassButton>
      </div>
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
    </SettingsSection>
  );
}
