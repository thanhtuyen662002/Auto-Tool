import type { HTMLAttributes, ReactNode } from 'react';

type Props = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  hover?: boolean;
  active?: boolean;
  strong?: boolean;
};

export default function GlassCard({ children, className = '', hover, active, strong, ...props }: Props) {
  return (
    <div
      className={`${strong ? 'glass-card-strong' : 'glass-card'} ${hover ? 'transition hover:-translate-y-0.5 hover:border-cyan-300/35' : ''} ${active ? 'border-cyan-300/60 bg-cyan-300/10 glow-primary' : ''} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
