import { ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export default function GlassPagination({ currentPage, totalPages, onPageChange, className = '' }: Props) {
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (currentPage > 3) pages.push(-1); // -1 represents ellipsis

    const start = Math.max(2, currentPage - 1);
    const end = Math.min(totalPages - 1, currentPage + 1);

    for (let i = start; i <= end; i++) {
      if (!pages.includes(i)) pages.push(i);
    }

    if (currentPage < totalPages - 2) pages.push(-2); // -2 represents ellipsis
    pages.push(totalPages);
  }

  return (
    <div className={`flex items-center justify-center gap-2 mt-6 ${className}`}>
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="flex h-9 w-9 items-center justify-center rounded-md border border-white/10 bg-white/5 text-slate-300 transition hover:border-cyan-300/30 hover:bg-white/10 hover:text-white disabled:opacity-40 disabled:hover:border-white/10 disabled:hover:bg-white/5"
        title="Trang trước"
      >
        <ChevronLeft size={16} />
      </button>

      {pages.map((p, idx) => {
        if (p < 0) {
          return (
            <span key={`ell-${idx}`} className="px-2 text-slate-500 select-none">
              ...
            </span>
          );
        }

        const isActive = p === currentPage;
        return (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`flex h-9 min-w-9 items-center justify-center rounded-md border px-3 text-sm font-semibold transition ${
              isActive
                ? 'border-cyan-300/50 bg-cyan-300 text-slate-950 glow-primary font-bold'
                : 'border-white/10 bg-white/5 text-slate-300 hover:border-cyan-300/30 hover:bg-white/10 hover:text-white'
            }`}
          >
            {p}
          </button>
        );
      })}

      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="flex h-9 w-9 items-center justify-center rounded-md border border-white/10 bg-white/5 text-slate-300 transition hover:border-cyan-300/30 hover:bg-white/10 hover:text-white disabled:opacity-40 disabled:hover:border-white/10 disabled:hover:bg-white/5"
        title="Trang sau"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
