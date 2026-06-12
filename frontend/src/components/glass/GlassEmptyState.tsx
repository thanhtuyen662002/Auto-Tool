import { FolderOpen } from 'lucide-react';
import type { ReactNode } from 'react';
import GlassCard from './GlassCard';

export default function GlassEmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <GlassCard className="p-8 text-center" strong>
      <FolderOpen className="mx-auto text-cyan-200" size={30} />
      <h3 className="mt-4 text-base font-semibold text-white">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-300">{message}</p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </GlassCard>
  );
}
