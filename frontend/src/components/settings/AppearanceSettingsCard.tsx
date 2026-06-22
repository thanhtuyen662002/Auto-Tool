import { useMemo, useState } from 'react';
import { browsePath } from '../../api/client';
import GlassButton from '../glass/GlassButton';
import GlassSelect from '../glass/GlassSelect';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SettingsSection from './SettingsSection';
import {
  applyAppearanceSettings,
  getLocalUiSettings,
  resolveBackgroundImageUrl,
  saveLocalUiSettings,
  type GlassIntensity,
  type LayoutDensity,
  type LocalUiSettings,
} from '../../utils/localSettings';

export default function AppearanceSettingsCard() {
  const initial = useMemo(() => getLocalUiSettings(), []);
  const [settings, setSettings] = useState<LocalUiSettings>(initial);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const backgroundPreviewUrl = settings.backgroundImageEnabled && settings.backgroundImageSource.trim()
    ? resolveBackgroundImageUrl(settings)
    : '';

  function update(updates: Partial<LocalUiSettings>) {
    setSettings((current) => ({ ...current, ...updates }));
  }

  function save() {
    saveLocalUiSettings(settings);
    applyAppearanceSettings(settings);
    setMessage('Đã lưu và áp dụng giao diện.');
  }

  function preview() {
    applyAppearanceSettings(settings);
    setMessage('Đang xem thử giao diện. Bấm Lưu để giữ cho lần mở sau.');
  }

  async function chooseLocalBackground() {
    setBusy(true);
    try {
      const response = await browsePath({
        mode: 'file',
        title: 'Chọn ảnh nền cho Auto Tool',
        initial_path: settings.backgroundImageSource || null,
        extensions: ['.png', '.jpg', '.jpeg', '.webp'],
      });
      if (!response.cancelled && response.path) {
        update({
          backgroundImageMode: 'local',
          backgroundImageSource: response.path,
          backgroundImageEnabled: true,
        });
        setMessage('Đã chọn ảnh nền. Bấm Xem thử hoặc Lưu để áp dụng.');
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Không mở được hộp thoại chọn ảnh nền.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <SettingsSection title="Giao diện & Theme" description="Đổi giao diện sáng/tối, tự chọn màu chữ, màu thẻ và ảnh nền theo ý người dùng.">
      <div className="grid gap-3 lg:grid-cols-3">
        <ThemeChoice
          active={settings.themeMode === 'dark'}
          title="Tối mặc định"
          description="Giao diện tối hiện tại, dễ dùng khi render lâu."
          onClick={() => update({ themeMode: 'dark' })}
        />
        <ThemeChoice
          active={settings.themeMode === 'light'}
          title="Sáng dễ nhìn"
          description="Nền sáng, chữ tối, phù hợp phòng sáng và màn hình văn phòng."
          onClick={() => update({ themeMode: 'light' })}
        />
        <ThemeChoice
          active={settings.themeMode === 'custom'}
          title="Tùy chỉnh"
          description="Tự chọn màu nền, màu chữ, màu thẻ, viền và màu nhấn."
          onClick={() => update({ themeMode: 'custom' })}
        />
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <GlassSelect label="Độ đậm kính mờ" value={settings.glassIntensity} onChange={(event) => update({ glassIntensity: event.target.value as GlassIntensity })}>
          <option value="soft">Nhẹ nhàng</option>
          <option value="medium">Vừa phải</option>
          <option value="strong">Đậm nét</option>
        </GlassSelect>
        <GlassSelect label="Mật độ bố cục" value={settings.layoutDensity} onChange={(event) => update({ layoutDensity: event.target.value as LayoutDensity })}>
          <option value="comfortable">Dễ nhìn</option>
          <option value="compact">Gọn gàng</option>
        </GlassSelect>
        <label className="flex min-h-11 items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
          <input type="checkbox" checked={settings.reduceMotion} onChange={(event) => update({ reduceMotion: event.target.checked })} />
          Giảm chuyển động
        </label>
      </div>

      {settings.themeMode === 'custom' ? (
        <div className="mt-5 grid gap-3 rounded-md border border-white/10 bg-black/15 p-4 lg:grid-cols-4">
          <ColorField label="Màu nền" value={settings.customBackgroundColor} onChange={(value) => update({ customBackgroundColor: value })} />
          <ColorField label="Màu chữ chính" value={settings.customTextColor} onChange={(value) => update({ customTextColor: value })} />
          <ColorField label="Màu chữ phụ" value={settings.customMutedTextColor} onChange={(value) => update({ customMutedTextColor: value })} />
          <ColorField label="Màu nhấn/nút" value={settings.customAccentColor} onChange={(value) => update({ customAccentColor: value })} />
          <ColorField label="Màu thẻ chính" value={settings.customCardColor} onChange={(value) => update({ customCardColor: value })} />
          <ColorField label="Màu thẻ phụ" value={settings.customCardSoftColor} onChange={(value) => update({ customCardSoftColor: value })} />
          <ColorField label="Màu viền thẻ" value={settings.customBorderColor} onChange={(value) => update({ customBorderColor: value })} />
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 rounded-md border border-white/10 bg-black/15 p-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Ảnh nền tùy chỉnh</h3>
              <p className="mt-1 text-xs leading-5 text-slate-400">Chọn ảnh trên máy hoặc nhập URL ảnh. Tool sẽ nhớ lựa chọn cho các lần mở sau.</p>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-200">
              <input
                type="checkbox"
                checked={settings.backgroundImageEnabled}
                onChange={(event) => update({
                  backgroundImageEnabled: event.target.checked,
                  backgroundImageMode: event.target.checked && settings.backgroundImageMode === 'none' ? 'local' : settings.backgroundImageMode,
                })}
              />
              Bật ảnh nền
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <GlassButton variant="secondary" loading={busy} onClick={() => void chooseLocalBackground()}>
              Chọn ảnh từ máy
            </GlassButton>
            <GlassButton
              variant={settings.backgroundImageMode === 'url' ? 'primary' : 'secondary'}
              onClick={() => update({ backgroundImageMode: 'url', backgroundImageEnabled: true })}
            >
              Dùng URL ảnh
            </GlassButton>
            <GlassButton
              variant="ghost"
              onClick={() => update({ backgroundImageMode: 'none', backgroundImageSource: '', backgroundImageEnabled: false })}
            >
              Xóa ảnh nền
            </GlassButton>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-200">
              {settings.backgroundImageMode === 'url' ? 'URL ảnh nền' : 'Đường dẫn ảnh nền'}
            </span>
            <input
              className="h-11 w-full rounded-md border border-white/15 bg-slate-950/75 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
              placeholder={settings.backgroundImageMode === 'url' ? 'https://...' : 'Chưa chọn ảnh nền'}
              readOnly={settings.backgroundImageMode !== 'url'}
              value={settings.backgroundImageSource}
              onChange={(event) => update({ backgroundImageSource: event.target.value, backgroundImageMode: 'url', backgroundImageEnabled: Boolean(event.target.value.trim()) })}
            />
          </label>
          <div className="grid gap-3 lg:grid-cols-3">
            <RangeField label="Độ hiện ảnh nền" value={settings.backgroundImageOpacity} min={0} max={0.8} step={0.01} onChange={(value) => update({ backgroundImageOpacity: value })} />
            <RangeField label="Làm mờ ảnh nền" value={settings.backgroundImageBlur} min={0} max={24} step={1} unit="px" onChange={(value) => update({ backgroundImageBlur: value })} />
            <RangeField label="Lớp phủ dễ đọc" value={settings.backgroundImageOverlayOpacity} min={0} max={0.9} step={0.01} onChange={(value) => update({ backgroundImageOverlayOpacity: value })} />
          </div>
        </div>
        <div
          className="min-h-56 overflow-hidden rounded-md border border-white/10 bg-slate-950/70 p-4"
          style={backgroundPreviewUrl ? {
            backgroundImage: `linear-gradient(rgba(0,0,0,0.22), rgba(0,0,0,0.22)), url("${backgroundPreviewUrl.replace(/"/g, '\\"')}")`,
            backgroundPosition: 'center',
            backgroundSize: 'cover',
          } : undefined}
        >
          <div className="rounded-md border border-white/15 bg-black/35 p-4 backdrop-blur">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">Preview</div>
            <div className="mt-2 text-lg font-semibold text-white">Auto Tool Studio</div>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Đây là bản xem nhanh để kiểm tra màu chữ, màu thẻ và ảnh nền có đủ dễ đọc hay không.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <GlassButton variant="secondary" onClick={preview} className="hover:scale-[1.02] active:scale-[0.98] transition-all">Xem thử</GlassButton>
        <GlassButton variant="primary" onClick={save} className="hover:scale-[1.02] active:scale-[0.98] transition-all">Lưu giao diện</GlassButton>
      </div>
      <NotifyOnChange value={message} variant="success" />
      {message ? <div className="mt-3 text-sm text-emerald-200">{message}</div> : null}
    </SettingsSection>
  );
}

function ThemeChoice({
  active,
  title,
  description,
  onClick,
}: {
  active: boolean;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={`rounded-md border p-4 text-left transition ${
        active
          ? 'border-cyan-300/60 bg-cyan-300/12 text-white'
          : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-300/35 hover:bg-white/8'
      }`}
      type="button"
      onClick={onClick}
    >
      <span className="text-sm font-semibold">{title}</span>
      <span className="mt-2 block text-xs leading-5 text-slate-400">{description}</span>
    </button>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span>
      <div className="flex gap-2">
        <input
          className="h-11 w-14 rounded-md border border-white/15 bg-slate-950/75 p-1"
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <input
          className="h-11 min-w-0 flex-1 rounded-md border border-white/15 bg-slate-950/75 px-3 text-sm text-white outline-none focus:border-cyan-300/70 focus:ring-2 focus:ring-cyan-300/15"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    </label>
  );
}

function RangeField({
  label,
  value,
  min,
  max,
  step,
  unit = '',
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (value: number) => void;
}) {
  const displayValue = unit ? `${value}${unit}` : `${Math.round(value * 100)}%`;
  return (
    <label className="block rounded-md border border-white/10 bg-white/5 p-3">
      <span className="flex items-center justify-between gap-2 text-sm font-medium text-slate-200">
        <span>{label}</span>
        <span className="rounded-md border border-white/10 bg-black/20 px-2 py-1 text-xs text-slate-300">{displayValue}</span>
      </span>
      <input
        className="mt-3 w-full accent-cyan-300"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
