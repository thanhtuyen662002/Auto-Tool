import { useMemo, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassInput from '../glass/GlassInput';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SettingsSection from './SettingsSection';
import { API_BASE_URL } from '../../services/api';
import { getLocalUiSettings, resetLocalUiSettings, saveLocalUiSettings } from '../../utils/localSettings';

export default function AdvancedTechnicalSettings() {
  const initial = useMemo(() => getLocalUiSettings(), []);
  const [open, setOpen] = useState(false);
  const [debugUi, setDebugUi] = useState(initial.debugUi);
  const [showRawJson, setShowRawJson] = useState(initial.showRawJson);
  const [pollingInterval, setPollingInterval] = useState(initial.pollingInterval);
  const [message, setMessage] = useState<string | null>(null);

  function save() {
    saveLocalUiSettings({ debugUi, showRawJson, pollingInterval });
    setMessage('Đã lưu thiết lập kỹ thuật.');
  }

  function reset() {
    resetLocalUiSettings();
    setMessage('Đã khôi phục cài đặt giao diện mặc định. Tải lại trang nếu muốn thấy toàn bộ thay đổi.');
  }

  return (
    <SettingsSection title="Cấu hình nâng cao" description="Các thiết lập này dành cho kiểm tra sâu hoặc hỗ trợ kỹ thuật. Nếu không chắc, hãy giữ mặc định.">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-md border border-white/10 bg-black/15 px-4 py-3 text-left text-sm font-semibold text-white hover:bg-white/8"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        Cài đặt nâng cao
        <span className="text-xs text-slate-400">{open ? 'Đóng' : 'Mở'}</span>
      </button>
      {open ? (
        <div className="mt-4 grid gap-4">
          <GlassInput label="Địa chỉ bộ xử lý nội bộ" value={API_BASE_URL} readOnly />
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
              <input type="checkbox" checked={debugUi} onChange={(event) => setDebugUi(event.target.checked)} />
              Bật chế độ kiểm tra giao diện
            </label>
            <label className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-200">
              <input type="checkbox" checked={showRawJson} onChange={(event) => setShowRawJson(event.target.checked)} />
              Hiển thị dữ liệu kỹ thuật thô
            </label>
          </div>
          <GlassInput
            label="Khoảng thời gian tự cập nhật (giây)"
            type="number"
            min={1}
            value={pollingInterval}
            onChange={(event) => setPollingInterval(Math.max(1, Number(event.target.value || 1)))}
          />
          <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
            Nhật ký kỹ thuật và dữ liệu thô mặc định được ẩn. Chỉ bật khi cần kiểm tra lỗi sâu hoặc gửi thông tin cho người hỗ trợ.
          </div>
          <div className="flex flex-wrap gap-2">
            <GlassButton variant="primary" onClick={save}>Lưu cấu hình nâng cao</GlassButton>
            <GlassButton variant="danger" onClick={reset}>Khôi phục giao diện mặc định</GlassButton>
          </div>
          <NotifyOnChange value={message} variant="success" />
          {message ? <div className="text-sm text-emerald-200">{message}</div> : null}
        </div>
      ) : null}
    </SettingsSection>
  );
}
