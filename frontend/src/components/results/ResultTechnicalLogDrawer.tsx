import { Clipboard, X } from 'lucide-react';
import type { ReactNode } from 'react';
import type { JobStatus } from '../../types/project';
import { copyText, type NormalizedResultItem } from '../../utils/resultStatus';
import GlassButton from '../glass/GlassButton';
import { emitNotification } from '../notifications/NotificationProvider';

export default function ResultTechnicalLogDrawer({
  open,
  item,
  jobStatus,
  onClose,
}: {
  open: boolean;
  item: NormalizedResultItem | null;
  jobStatus: JobStatus | null;
  onClose: () => void;
}) {
  if (!open) return null;
  const copyPayload = item
    ? JSON.stringify({ index: item.index, status: item.rawStatus, path: item.path, files: item.files, warnings: item.warnings, errors: item.errors, qa: item.qa }, null, 2)
    : JSON.stringify(jobStatus ?? { status: 'unknown' }, null, 2);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/55" role="dialog" aria-modal="true" aria-label="Nhật ký xử lý">
      <button className="hidden flex-1 cursor-default md:block" type="button" aria-label="Đóng nhật ký" onClick={onClose} />
      <aside className="h-full w-full max-w-xl overflow-auto border-l border-white/10 bg-slate-950/95 p-5 shadow-2xl backdrop-blur">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-white">Nhật ký xử lý</h2>
            <p className="mt-1 truncate text-sm text-slate-400">{item?.filename ?? jobStatus?.job_id ?? 'Chi tiết công việc'}</p>
          </div>
          <button className="rounded-md p-2 text-slate-300 hover:bg-white/10 hover:text-white" type="button" onClick={onClose} aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <GlassButton className="px-3" variant="secondary" onClick={() => void copyAndNotify(copyPayload)}>
            <Clipboard size={15} />
            Copy JSON
          </GlassButton>
          {item?.path ? (
            <GlassButton className="px-3" variant="ghost" onClick={() => void copyAndNotify(item.path)}>
              Copy đường dẫn video
            </GlassButton>
          ) : null}
        </div>

        {item ? (
          <div className="mt-5 grid gap-5">
            <Section title="Danh sách File">
              {item.files.length ? item.files.map((file) => <PathRow key={`${file.label}-${file.path}`} label={file.label} value={file.path} />) : <EmptyLine text="Không có file liên quan." />}
            </Section>
            <Section title="Cảnh báo">
              {item.warnings.length ? item.warnings.map((warning, index) => <LogLine key={`${warning}-${index}`} tone="warning" text={warning} />) : <EmptyLine text="Không có cảnh báo." />}
            </Section>
            <Section title="Lỗi">
              {item.errors.length ? item.errors.map((error, index) => <LogLine key={`${error}-${index}`} tone="error" text={error} />) : <EmptyLine text="Không có lỗi." />}
            </Section>
            <Section title="Kiểm tra chất lượng cuối">
              {item.qa?.issues.length ? item.qa.issues.map((issue, index) => <LogLine key={`${issue.issue_type}-${index}`} tone={issue.severity === 'critical' ? 'error' : 'warning'} text={`${issue.message}${issue.suggestion ? ` Gợi ý: ${issue.suggestion}` : ''}`} />) : <EmptyLine text={item.qa ? 'Không phát hiện vấn đề.' : 'Chưa chạy kiểm tra.'} />}
            </Section>
          </div>
        ) : null}

        <Section title="Nhật ký công việc" className="mt-5">
          {jobStatus?.logs?.length ? (
            jobStatus.logs.slice(-20).reverse().map((log) => (
              <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs leading-5" key={`${log.created_at}-${log.message}`}>
                <div className="font-semibold text-slate-200">{log.level} · {log.created_at}</div>
                <div className="mt-1 text-slate-400">{log.message}</div>
              </div>
            ))
          ) : (
            <EmptyLine text="Chưa có nhật ký công việc trong dữ liệu hiện tại." />
          )}
        </Section>
      </aside>
    </div>
  );
}

function Section({ title, className = '', children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <section className={`grid gap-2 ${className}`}>
      <h3 className="text-sm font-semibold uppercase tracking-normal text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

function PathRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid min-w-0 gap-1 rounded-md border border-white/10 bg-white/5 p-3 text-xs">
      <div className="font-semibold text-slate-300">{label}</div>
      <button className="break-all text-left text-slate-400 hover:text-cyan-200" type="button" onClick={() => void copyAndNotify(value)}>
        {value}
      </button>
    </div>
  );
}

async function copyAndNotify(value: string) {
  await copyText(value);
  emitNotification({ variant: 'success', message: 'Đã sao chép.' });
}

function LogLine({ text, tone }: { text: string; tone: 'warning' | 'error' }) {
  return <div className={`rounded-md border p-3 text-xs leading-5 ${tone === 'error' ? 'border-rose-300/20 bg-rose-400/10 text-rose-100' : 'border-amber-300/20 bg-amber-400/10 text-amber-100'}`}>{text}</div>;
}

function EmptyLine({ text }: { text: string }) {
  return <div className="rounded-md border border-white/10 bg-white/5 p-3 text-xs text-slate-500">{text}</div>;
}
