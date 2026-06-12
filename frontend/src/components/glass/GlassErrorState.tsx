import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

export default function GlassErrorState({
  title = 'Không thể tải dữ liệu',
  message,
  action,
  technicalLog,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
  technicalLog?: string;
}) {
  return (
    <div className="rounded-lg border border-rose-300/25 bg-rose-400/10 p-4 text-rose-100">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 shrink-0" size={18} />
        <div className="min-w-0">
          <div className="font-semibold">{title}</div>
          <div className="mt-1 text-sm leading-6 text-rose-100/80">{message}</div>
          {action ? <div className="mt-3">{action}</div> : null}
          {technicalLog ? (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-semibold text-rose-100">Xem log kỹ thuật</summary>
              <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded-md bg-black/30 p-3 text-xs text-rose-100/75">{technicalLog}</pre>
            </details>
          ) : null}
        </div>
      </div>
    </div>
  );
}
