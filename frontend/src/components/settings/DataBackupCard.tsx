import { useEffect, useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassInput from '../glass/GlassInput';
import { emitNotification } from '../notifications/NotificationProvider';
import NotifyOnChange from '../notifications/NotifyOnChange';
import SettingsSection from './SettingsSection';
import {
  createBackup,
  listBackups,
  type BackupListItem,
  type BackupRequest,
  type BackupResult,
} from '../../services/dataManagementApi';
import { revealFile } from '../../services/localAppApi';
import { formatBytes } from '../../utils/formatBytes';

const defaultRequest: BackupRequest = {
  include_config: true,
  include_database: true,
  include_projects: true,
  include_outputs: false,
  include_exports: true,
  include_subtitles: true,
  include_logs: false,
  backup_name: '',
  backup_folder: '',
};

export default function DataBackupCard() {
  const [request, setRequest] = useState<BackupRequest>(defaultRequest);
  const [result, setResult] = useState<BackupResult | null>(null);
  const [backups, setBackups] = useState<BackupListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resultMessage = result
    ? result.success
      ? 'Đã tạo bản sao lưu.'
      : 'Tạo bản sao lưu thất bại.'
    : null;

  useEffect(() => {
    void refreshBackups();
  }, []);

  async function refreshBackups() {
    try {
      const response = await listBackups();
      setBackups(response.items);
    } catch {
      setBackups([]);
    }
  }

  async function handleCreate() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await createBackup({ ...request, backup_name: request.backup_name || null, backup_folder: request.backup_folder || null });
      setResult(response);
      await refreshBackups();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tạo bản sao lưu.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SettingsSection title="Sao lưu Dữ liệu" description="Tạo file sao lưu dạng zip. Mặc định không sao lưu video kết quả để tránh file quá nặng.">
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="grid gap-3">
          <Toggle label="Cấu hình & thiết lập" checked={request.include_config} onChange={(value) => setRequest({ ...request, include_config: value })} />
          <Toggle label="Cơ sở dữ liệu / metadata dự án" checked={request.include_database} onChange={(value) => setRequest({ ...request, include_database: value })} />
          <Toggle label="Ví dụ & metadata dự án" checked={request.include_projects} onChange={(value) => setRequest({ ...request, include_projects: value })} />
          <Toggle label="Dữ liệu duyệt phụ đề" checked={request.include_subtitles} onChange={(value) => setRequest({ ...request, include_subtitles: value })} />
          <Toggle label="Các gói xuất dữ liệu" checked={request.include_exports} onChange={(value) => setRequest({ ...request, include_exports: value })} />
          <Toggle label="Các video kết quả cuối cùng" checked={request.include_outputs} onChange={(value) => setRequest({ ...request, include_outputs: value })} warning="Có thể làm file sao lưu rất nặng." />
          <Toggle label="Nhật ký hoạt động" checked={request.include_logs} onChange={(value) => setRequest({ ...request, include_logs: value })} />
          <GlassInput label="Tên bản sao lưu tùy chọn" value={request.backup_name ?? ''} onChange={(event) => setRequest({ ...request, backup_name: event.target.value })} />
          <GlassButton variant="primary" loading={loading} onClick={() => void handleCreate()}>
            Tạo bản sao lưu
          </GlassButton>
          <NotifyOnChange value={error} variant="error" />
          <NotifyOnChange value={resultMessage} variant={result?.success ? 'success' : 'error'} />
          {error ? <Notice tone="error" text={error} /> : null}
          {result ? (
            <div className="rounded-md border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-100">
              <div className="font-semibold">{result.success ? 'Đã tạo bản sao lưu' : 'Tạo bản sao lưu thất bại'}</div>
              {result.backup_path ? <PathLine path={result.backup_path} /> : null}
              <div>Kích thước: {formatBytes(result.size_bytes)}</div>
              {result.warnings.map((warning) => <div key={warning}>Cảnh báo: {warning}</div>)}
              {result.errors.map((item) => <div key={item}>Lỗi: {item}</div>)}
            </div>
          ) : null}
        </div>
        <div className="rounded-md border border-white/10 bg-black/15 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="font-semibold text-white">Bản sao lưu gần đây</h3>
            <GlassButton variant="ghost" onClick={() => void refreshBackups()}>Làm mới</GlassButton>
          </div>
          <div className="grid gap-2">
            {backups.length ? backups.slice(0, 6).map((backup) => (
              <div key={backup.path} className="rounded-md border border-white/10 bg-slate-950/40 p-3 text-sm text-slate-300">
                <div className="font-mono text-xs text-slate-100">{backup.path.split(/[\\/]/).pop()}</div>
                <div className="mt-1">{formatBytes(backup.size_bytes)} · {backup.created_at ?? 'Không rõ thời gian'}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <GlassButton variant="ghost" onClick={() => void copy(backup.path)}>Sao chép đường dẫn</GlassButton>
                  <GlassButton variant="ghost" onClick={() => void revealFile(backup.path)}>Mở thư mục</GlassButton>
                </div>
              </div>
            )) : <div className="text-sm text-slate-400">Chưa có backup nào.</div>}
          </div>
        </div>
      </div>
    </SettingsSection>
  );
}

function Toggle({ label, checked, onChange, warning }: { label: string; checked: boolean; onChange: (value: boolean) => void; warning?: string }) {
  return (
    <label className="flex items-start gap-3 rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-200">
      <input className="mt-1 h-4 w-4" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>
        <span className="font-medium">{label}</span>
        {warning ? <span className="ml-2 text-amber-200">{warning}</span> : null}
      </span>
    </label>
  );
}

function PathLine({ path }: { path: string }) {
  return (
    <div className="mt-2 break-all">
      Path: {path}
      <div className="mt-2 flex flex-wrap gap-2">
        <GlassButton variant="ghost" onClick={() => void copy(path)}>Sao chép đường dẫn</GlassButton>
        <GlassButton variant="ghost" onClick={() => void revealFile(path)}>Mở thư mục</GlassButton>
      </div>
    </div>
  );
}

function Notice({ tone, text }: { tone: 'error'; text: string }) {
  return <div className="rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100">{text}</div>;
}

async function copy(value: string) {
  await navigator.clipboard?.writeText(value);
  emitNotification({ variant: 'success', message: 'Đã sao chép đường dẫn backup.' });
}
