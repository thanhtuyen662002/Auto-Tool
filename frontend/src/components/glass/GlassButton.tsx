import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: Variant;
  loading?: boolean;
};

const variants: Record<Variant, string> = {
  primary: 'border-cyan-300/50 bg-cyan-300 text-slate-950 hover:bg-cyan-200',
  secondary: 'border-white/15 bg-white/8 text-white hover:border-cyan-300/45 hover:bg-white/12',
  ghost: 'border-transparent bg-transparent text-slate-300 hover:bg-white/8 hover:text-white',
  danger: 'border-rose-400/40 bg-rose-400/12 text-rose-200 hover:bg-rose-400/20',
};

export default function GlassButton({ children, variant = 'secondary', loading, className = '', disabled, ...props }: Props) {
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-cyan-300/40 disabled:opacity-50 ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <span className="h-4 w-4 animate-pulse rounded-full bg-current/50" /> : null}
      {children}
    </button>
  );
}
