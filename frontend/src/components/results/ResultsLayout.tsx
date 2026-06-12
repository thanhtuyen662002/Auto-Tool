import type { ReactNode } from 'react';
import GlassBadge from '../glass/GlassBadge';

export default function ResultsLayout({
  title,
  subtitle,
  statusLabel,
  actions,
  summary,
  children,
  sidePanel,
}: {
  title: string;
  subtitle: string;
  statusLabel?: string;
  actions?: ReactNode;
  summary?: ReactNode;
  children: ReactNode;
  sidePanel?: ReactNode;
}) {
  return (
    <main className="studio-page grid gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold text-white">{title}</h1>
            {statusLabel ? <GlassBadge variant="processing">{statusLabel}</GlassBadge> : null}
          </div>
          <p className="mt-1 break-all text-sm text-slate-400">{subtitle}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </header>
      {summary}
      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-w-0">{children}</section>
        {sidePanel ? <aside className="min-w-0">{sidePanel}</aside> : null}
      </div>
    </main>
  );
}
