import type { ReactNode } from 'react';
import GlassCard from '../glass/GlassCard';

export default function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <GlassCard strong className="p-5">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {description ? <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p> : null}
      </div>
      {children}
    </GlassCard>
  );
}
