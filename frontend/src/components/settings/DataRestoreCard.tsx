import { useState } from 'react';
import GlassButton from '../glass/GlassButton';
import GlassModal from '../glass/GlassModal';
import PathInput from '../PathInput';
import SettingsSection from './SettingsSection';
import {
  inspectBackup,
  restoreBackup,
  type BackupInspectResult,
  type RestoreRequest,
  type RestoreResult,
} from '../../services/dataManagementApi';
import { formatBytes } from '../../utils/formatBytes';

const defaultRestore: RestoreRequest = {
  backup_path: '',
  restore_config: true,
  restore_database: true,
  restore_projects: true,
  restore_outputs: false,
  restore_exports: true,
  restore_subtitles: true,
  restore_logs: false,
  create_pre_restore_backup: true,
  overwrite_existing: false,
};

export default function DataRestoreCard() {
  const [request, setRequest] = useState<RestoreRequest>(defaultRestore);
  const [inspect, setInspect] = useState<BackupInspectResult | null>(null);
  const [result, setResult] = useState<RestoreResult | null>(null);
  const [restoreConfirmOpen, setRestoreConfirmOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleInspect() {
    setLoading(true);
    setError(null);
    setInspect(null);
    try {
      setInspect(await inspectBackup(request.backup_path));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể kiểm tra backup.');
    } finally {
      setLoading(false);
    }
  }

  async function handleRestore() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await restoreBackup(request));
      setRestoreConfirmOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể restore backup.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SettingsSection title="Restore Backup" description="Kiểm tra backup trước khi restore. Mặc định tạo pre-restore backup và không ghi đè file đang có.">
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="grid gap-3">
          <PathInput
            label="Backup file path"
            value={request.backup_path}
            onChange={(backup_path) => {
              setRequest({ ...request, backup_path });
              setInspect(null);
              setRestoreConfirmOpen(false);
            }}
            modes={['file']}
            fileExtensions={['.zip']}
          />
          <GlassButton loading={loading} onClick={() => void handleInspect()}>Inspect Backup</GlassButton>
          {inspect ? (
            <div className="rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-300">
              <div className="font-semibold text-white">{inspect.success ? 'Backup hợp lệ' : 'Backup có lỗi'}</div>
              <div>Size: {formatBytes(inspect.size_bytes)} · Files: {inspect.file_count}</div>
              <div>Categories: {inspect.included_categories.join(', ') || 'Không rõ'}</div>
              {inspect.manifest ? <div>Created: {String(inspect.manifest.created_at ?? 'Không rõ')}</div> : null}
              {inspect.errors.map((item) => <div key={item} className="text-rose-200">Lỗi: {item}</div>)}
              {inspect.warnings.map((item) => <div key={item} className="text-amber-200">Cảnh báo: {item}</div>)}
            </div>
          ) : null}
          {error ? <div className="rounded-md border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-100">{error}</div> : null}
        </div>
        <div className="grid gap-3">
          <RestoreToggle label="Restore config" checked={request.restore_config} onChange={(restore_config) => setRequest({ ...request, restore_config })} />
          <RestoreToggle label="Restore database/project metadata" checked={request.restore_database} onChange={(restore_database) => setRequest({ ...request, restore_database })} />
          <RestoreToggle label="Restore subtitles" checked={request.restore_subtitles} onChange={(restore_subtitles) => setRequest({ ...request, restore_subtitles })} />
          <RestoreToggle label="Restore exports" checked={request.restore_exports} onChange={(restore_exports) => setRequest({ ...request, restore_exports })} />
          <RestoreToggle label="Restore logs" checked={request.restore_logs} onChange={(restore_logs) => setRequest({ ...request, restore_logs })} />
          <RestoreToggle label="Restore outputs" checked={request.restore_outputs} onChange={(restore_outputs) => setRequest({ ...request, restore_outputs })} />
          <RestoreToggle label="Create backup before restore" checked={request.create_pre_restore_backup} onChange={(create_pre_restore_backup) => setRequest({ ...request, create_pre_restore_backup })} />
          <RestoreToggle label="Overwrite existing files" checked={request.overwrite_existing} onChange={(overwrite_existing) => setRequest({ ...request, overwrite_existing })} />
          <div className="rounded-md border border-amber-400/25 bg-amber-400/10 p-3 text-sm leading-6 text-amber-100">
            Restore có thể ghi dữ liệu vào project hiện tại. Nên giữ bật tùy chọn tạo pre-restore backup.
          </div>
          <GlassButton variant="danger" loading={loading} disabled={!inspect?.success} onClick={() => setRestoreConfirmOpen(true)}>
            Restore Backup
          </GlassButton>
          {result ? (
            <div className="rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-300">
              <div className={result.success ? 'text-emerald-200' : 'text-rose-200'}>{result.success ? 'Restore completed' : 'Restore failed'}</div>
              <div>Restored: {result.restored_categories.join(', ') || 'Không có file nào được ghi'}</div>
              {result.pre_restore_backup_path ? <div className="break-all">Pre-restore backup: {result.pre_restore_backup_path}</div> : null}
              {result.warnings.map((item) => <div key={item} className="text-amber-200">Cảnh báo: {item}</div>)}
              {result.errors.map((item) => <div key={item} className="text-rose-200">Lỗi: {item}</div>)}
            </div>
          ) : null}
        </div>
      </div>
      <GlassModal open={restoreConfirmOpen} title="Xác nhận restore backup" onClose={() => setRestoreConfirmOpen(false)}>
        <div className="grid gap-4 text-sm text-slate-300">
          <div className="rounded-md border border-amber-400/25 bg-amber-400/10 p-4 leading-6 text-amber-100">
            Restore có thể ghi đè dữ liệu hiện tại nếu bạn bật overwrite. Bạn nên giữ bật tùy chọn tạo pre-restore backup.
          </div>
          <div className="grid gap-2 rounded-md border border-white/10 bg-black/15 p-3">
            <div>Backup: <span className="break-all font-mono text-slate-100">{request.backup_path}</span></div>
            <div>Pre-restore backup: {request.create_pre_restore_backup ? 'Có' : 'Không'}</div>
            <div>Overwrite existing files: {request.overwrite_existing ? 'Có' : 'Không'}</div>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <GlassButton variant="ghost" onClick={() => setRestoreConfirmOpen(false)}>Cancel</GlassButton>
            <GlassButton variant="danger" loading={loading} onClick={() => void handleRestore()}>Restore</GlassButton>
          </div>
        </div>
      </GlassModal>
    </SettingsSection>
  );
}

function RestoreToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 rounded-md border border-white/10 bg-black/15 p-3 text-sm text-slate-200">
      <input className="h-4 w-4" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
