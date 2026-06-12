import type { ReactNode } from 'react';

export default function StartWorkflowLayout({
  hero,
  main,
  side,
  footer,
}: {
  hero: ReactNode;
  main: ReactNode;
  side: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="studio-page grid gap-6">
      {hero}
      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.62fr)]">
        <section className="grid min-w-0 gap-4">{main}</section>
        <aside className="grid min-w-0 content-start gap-4 xl:sticky xl:top-5">{side}</aside>
      </div>
      {footer}
    </div>
  );
}
