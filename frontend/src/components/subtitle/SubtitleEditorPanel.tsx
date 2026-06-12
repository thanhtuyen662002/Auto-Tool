import type { ReactNode } from 'react';
import GlassCard from '../glass/GlassCard';

export default function SubtitleEditorPanel({ title, count, children, actions }: { title: string; count: number; children: ReactNode; actions?: ReactNode }) { return <GlassCard className="min-w-0 p-4" strong><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold text-white">{title}</h2><p className="mt-1 text-xs text-slate-500">{count} dòng đang hiển thị</p></div>{actions}</div>{children}</GlassCard>; }
