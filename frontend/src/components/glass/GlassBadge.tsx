import type { ReactNode } from 'react';

export type GlassBadgeVariant = 'ready' | 'processing' | 'needs_review' | 'approved' | 'rendered' | 'warning' | 'failed' | 'success' | 'neutral';

const styles: Record<GlassBadgeVariant, string> = {
  ready: 'border-cyan-300/30 bg-cyan-300/10 text-cyan-200',
  processing: 'border-violet-300/30 bg-violet-300/10 text-violet-200',
  needs_review: 'border-amber-300/30 bg-amber-300/10 text-amber-200',
  approved: 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200',
  rendered: 'border-sky-300/30 bg-sky-300/10 text-sky-200',
  warning: 'border-amber-300/30 bg-amber-300/10 text-amber-200',
  failed: 'border-rose-300/30 bg-rose-300/10 text-rose-200',
  success: 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200',
  neutral: 'border-white/15 bg-white/7 text-slate-300',
};

export default function GlassBadge({ children, variant = 'neutral', className = '' }: { children: ReactNode; variant?: GlassBadgeVariant; className?: string }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[variant]} ${className}`}>{children}</span>;
}
