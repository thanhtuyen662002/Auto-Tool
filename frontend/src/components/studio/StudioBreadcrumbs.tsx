import { ChevronRight, Home } from 'lucide-react';
import { Link } from 'react-router-dom';

export type StudioBreadcrumbItem = {
  label: string;
  to?: string;
};

export default function StudioBreadcrumbs({ items }: { items: StudioBreadcrumbItem[] }) {
  if (!items.length) return null;

  return (
    <nav className="hidden items-center gap-1 text-xs text-slate-500 sm:flex" aria-label="Breadcrumb">
      <Link className="inline-flex items-center gap-1 hover:text-cyan-200" to="/">
        <Home size={13} />
        Tổng quan
      </Link>
      {items.map((item) => (
        <span className="inline-flex items-center gap-1" key={`${item.label}-${item.to ?? 'current'}`}>
          <ChevronRight size={13} />
          {item.to ? (
            <Link className="hover:text-cyan-200" to={item.to}>
              {item.label}
            </Link>
          ) : (
            <span className="text-slate-300">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
