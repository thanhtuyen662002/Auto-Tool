export default function SourceMediaSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="h-64 animate-pulse rounded-md border border-white/10 bg-white/8" />
      ))}
    </div>
  );
}
